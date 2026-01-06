import requests

# URL of the API
url = "http://127.0.0.1:8000/upload-report"

# Path to the file you want to upload
# Create a dummy file for testing if you don't have one
with open("test_report.pdf", "w") as f:
    f.write("This is a dummy PDF content.")

file_path = "test_report.pdf"

# Open the file in binary mode
with open(file_path, "rb") as file:
    files = {"file": file}
    response = requests.post(url, files=files)

# Print the response
print(f"Status Code: {response.status_code}")
print(f"Response JSON: {response.json()}")
