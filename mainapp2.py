from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import sqlite3
import os
from vertexai import init
from vertexai.generative_models import GenerativeModel
from google.cloud import aiplatform

# Initialize the Vertex AI client
project_id = "build-n-blog"  # Replace with your actual project ID
location = "us-central1"      # Replace with your desired region

aiplatform.init(project=project_id, location=location)

# Load the Text-Bison model (or the desired Generative AI model)
model = GenerativeModel("gemini-1.5-flash-002")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')  # Replace with a secure key

# Temporary database name
db_name = "temp_data.db"

@app.route('/')
def index():
    return render_template('mainindex2.html')

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

        # Validate the file's structure
        if data.empty or data.columns.size == 0:
            flash("The uploaded CSV file is empty or invalid.")
            return redirect(url_for('index'))

        # Load data into SQLite
        with sqlite3.connect(db_name) as conn:
            data.to_sql('uploaded_data', conn, if_exists='replace', index=False)

        # Extract schema information
        schema = ", ".join([f"{col} (type: {dtype})" for col, dtype in zip(data.columns, data.dtypes)])
        print(f"Schema: {schema}")  # Debugging

        # Construct the prompt for the generative model
        full_prompt = f"""
        You are a smart query generator for retail analytics. Based on the following dataset schema and user query, generate an SQL query:
        Dataset schema: {schema}
        User query: {prompt}
        """

        # Generate the SQL query
        response = model.generate_content(full_prompt)
        raw_query = response.text.strip()

        # Remove Markdown formatting and clean the query
       # Remove Markdown formatting and clean the query
        cleaned_query = raw_query.split("```")[1] if "```" in raw_query else raw_query  # Extract query block
        cleaned_query = cleaned_query.split("\n")[0] if "Note:" in cleaned_query else cleaned_query  # Remove 'Note' or extra info
        cleaned_query = cleaned_query.strip()  # Final cleanup of whitespace

# Ensure the query starts with 'SELECT' (or another valid SQL command)
        if cleaned_query.lower().startswith("sql"):
            cleaned_query = cleaned_query[3:].strip()  # Remove the 'sql' prefix if present

# Replace placeholder table name
        cleaned_query = cleaned_query.replace("your_table_name", "uploaded_data")


        # Remove Markdown formatting and explanations
       # cleaned_query = raw_query.split("```")[1] if "```" in raw_query else raw_query
        

       # cleaned_query = cleaned_query.split("\n")[0] if "Note:" in cleaned_query else cleaned_query

        # Debugging: Log queries
        print(f"Raw Query: {raw_query}")
        print(f"Cleaned Query: {cleaned_query}")

        # Execute the cleaned query
        try:
            with sqlite3.connect(db_name) as conn:
                result = pd.read_sql_query(cleaned_query, conn)
            
            # Convert result to HTML table
            result_html = result.to_html(classes='data-table', index=False)
            return render_template('mainindex2.html', query=cleaned_query, result=result_html)
        except Exception as e:
            flash(f"Error executing query: {str(e)}")
            return redirect(url_for('index'))

    flash("Invalid file type. Please upload a CSV file.")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)  # Run the app in debug mode for development
