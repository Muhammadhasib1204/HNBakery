from flask import Flask
from routes import init_routes
import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "skripsi_hnbakery")

init_routes(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))