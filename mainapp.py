from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import os
import sqlite3
from vertexai import init
from vertexai.generative_models import GenerativeModel
from google.cloud import aiplatform

# Initialize the Vertex AI client
project_id = "build-n-blog"  # Replace with your actual project ID
location = "us-central1"      # Replace with your desired region

aiplatform.init(project=project_id, location=location)

# Deploy the Text-Bison model (replace with the actual model ID)
model = GenerativeModel("gemini-1.5-flash-002")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')  # Replace with a secure key

# Path for SQLite database
DATABASE_PATH = "database.db"

@app.route('/')
def index():
    return render_template('mainindex2.html')  # Assuming index.html exists

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files or 'prompt' not in request.form:
        flash("No file or prompt provided!")
        return redirect(request.url)

    file = request.files['file']
    prompt = request.form['prompt']

    if file.filename == '':
        flash("No file selected!")
        return redirect(request.url)

    if file and file.filename.endswith('.csv'):
        # Read the CSV file
        data = pd.read_csv(file)

        # Validate the file's structure (optional)
        if data.empty or data.columns.size == 0:
            flash("The uploaded CSV file is empty or invalid.")
            return redirect(url_for('index'))

        # Create SQLite database and table
        conn = sqlite3.connect(DATABASE_PATH)
        try:
            # Create the transactions table from CSV
            data.to_sql("transactions", conn, if_exists="replace", index=False)
            conn.commit()  # Commit changes to make them available for queries

            # Extract schema information
            schema = ", ".join([f"{col} (type: {dtype})" for col, dtype in zip(data.columns, data.dtypes)])
            print(f"Schema: {schema}")  # Debugging

            # Construct the prompt for the text generation model
            full_prompt = f"""
            You are a smart query generator for retail analytics. Based on the following dataset schema and user query, generate an SQL query:
            Dataset schema: {schema}
            User query: {prompt}
            """

            # Generate the SQL query
            response = model.generate_content(full_prompt)

            # Remove Markdown formatting and clean the query
            raw_query = response
            cleaned_query = raw_query.split("```")[1] if "```" in raw_query else raw_query  # Extract query block
            cleaned_query = cleaned_query.split("\n")[0] if "Note:" in cleaned_query else cleaned_query  # Remove 'Note' or extra info
            cleaned_query = cleaned_query.strip()  # Final cleanup of whitespace

            # Ensure the query starts with 'SELECT' (or another valid SQL command)
            if cleaned_query.lower().startswith("sql"):
                cleaned_query = cleaned_query[3:].strip()  # Remove the 'sql' prefix if present

            # Execute the SQL query
            try:
                result = pd.read_sql_query(cleaned_query, conn)  # Execute query
                flash("Query executed successfully!")
                flash(f"Result: {result.head().to_html(classes='table table-striped')}")
            except Exception as e:
                flash(f"Error executing query: {str(e)}")
        except Exception as e:
            flash(f"Error processing the file or creating the database: {str(e)}")
        finally:
            conn.close()  # Ensure the connection is closed

        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)  # Run the app in debug mode for development
