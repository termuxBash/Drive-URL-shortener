from flask import Flask
from drive import drive_blueprint
#from admin import admin_blueprint  # If you have another

app = Flask(__name__)

# Each blueprint gets its own route prefix
app.register_blueprint(drive_blueprint, url_prefix="/drive")

if __name__ == "__main__":
    app.run(debug=True)
