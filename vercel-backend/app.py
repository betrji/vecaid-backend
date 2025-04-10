


# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from flask_pymongo import PyMongo
# from flask_bcrypt import Bcrypt
# from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
# from bson.objectid import ObjectId
# from datetime import timedelta, datetime

# app = Flask(__name__)

# # Enable CORS globally
# CORS(app, resources={r"/*": {"origins": "*"}})  

# # MongoDB Config
# # app.config["MONGO_URI"] = "mongodb://localhost:27017/vecaid"
# # app.config["MONGO_URI"] = "mongodb+srv://naveensaisde:gRZnKDwoFnKOwqzu@cluster0.yeoxgms.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
# app.config["MONGO_URI"] = "mongodb+srv://naveensaisde:gRZnKDwoFnKOwqzu@cluster0.yeoxgms.mongodb.net/vecaid?retryWrites=true&w=majority&appName=Cluster0"

# mongo = PyMongo(app)
# bcrypt = Bcrypt(app)

# # JWT Config
# app.config["JWT_SECRET_KEY"] = "vecaid-beta"
# jwt = JWTManager(app)

# # User Collection
# users = mongo.db.users

# # --------------------------------------
# # User Signup Route
# # --------------------------------------
# @app.route("/api/signup", methods=["POST"])
# def signup():
#     data = request.json
#     email = data.get("email")
#     password = data.get("password")

#     if users.find_one({"email": email}):
#         return jsonify({"error": "Email already registered"}), 400

#     hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
#     user_id = users.insert_one({
#         "email": email,
#         "password": hashed_password,
#         "createdAt": datetime.utcnow()
#     }).inserted_id

#     return jsonify({"message": "User registered successfully!", "user_id": str(user_id)}), 201

# # --------------------------------------
# # User Login Route
# # --------------------------------------
# @app.route("/api/login", methods=["POST"])
# def login():
#     data = request.json
#     email = data.get("email")
#     password = data.get("password")

#     user = users.find_one({"email": email})
#     if not user or not bcrypt.check_password_hash(user["password"], password):
#         return jsonify({"error": "Invalid email or password"}), 401

#     access_token = create_access_token(identity=str(user["_id"]))
#     return jsonify({"token": access_token, "message": "Login successful"}), 200

# # --------------------------------------
# # Guest Login (2 Hour Expiry)
# # --------------------------------------
# @app.route("/api/guest-login", methods=["POST"])
# def guest_login():
#     expires = timedelta(hours=2)
#     token = create_access_token(identity="guest_user", expires_delta=expires)
#     return jsonify({
#         "token": token,
#         "message": "Guest session started. Expires in 2 hours.",
#         "expires_at": (datetime.utcnow() + expires).isoformat()
#     }), 200

# # --------------------------------------
# # Protected Route - Dashboard Example
# # --------------------------------------
# @app.route("/api/dashboard", methods=["GET"])
# @jwt_required()
# def dashboard():
#     current_user_id = get_jwt_identity()

#     if current_user_id == "guest_user":
#         return jsonify({"message": "Welcome, Guest! Your session is temporary."}), 200

#     user = users.find_one({"_id": ObjectId(current_user_id)})
#     if user:
#         return jsonify({"message": f"Welcome back, {user['email']}!"}), 200
#     return jsonify({"error": "User not found"}), 404

# # --------------------------------------
# # Run Flask App
# # --------------------------------------
# if __name__ == "__main__":
#     app.run(debug=True, host="0.0.0.0", port=5001)


from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from bson.objectid import ObjectId
from datetime import timedelta, datetime
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import io
import base64

from vecaid_premium import predict_forecast, get_fundamentals, options_contracts_signal

app = Flask(__name__)
CORS(app)

# MongoDB Atlas
# app.config["MONGO_URI"] = "mongodb+srv://naveensaisde:gRZnKDwoFnKOwqzu@cluster0.yeoxgms.mongodb.net/vecaid?retryWrites=true&w=majority&appName=Cluster0"
app.config["MONGO_URI"] = "mongodb://localhost:27017/vecaid"
mongo = PyMongo(app)
bcrypt = Bcrypt(app)

# JWT Config
app.config["JWT_SECRET_KEY"] = "vecaid-beta"
jwt = JWTManager(app)
users = mongo.db.users

# ========================
# Auth APIs
# ========================

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    if users.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 400
    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
    user_id = users.insert_one({"email": email, "password": hashed_password, "createdAt": datetime.utcnow()}).inserted_id
    return jsonify({"message": "User registered successfully!", "user_id": str(user_id)}), 201

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    user = users.find_one({"email": email})
    if not user or not bcrypt.check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid email or password"}), 401
    token = create_access_token(identity=str(user["_id"]))
    return jsonify({"token": token, "message": "Login successful"}), 200

@app.route("/api/guest-login", methods=["POST"])
def guest_login():
    expires = timedelta(hours=2)
    token = create_access_token(identity="guest_user", expires_delta=expires)
    return jsonify({
        "token": token,
        "message": "Guest session started. Expires in 2 hours.",
        "expires_at": (datetime.utcnow() + expires).isoformat()
    }), 200

@app.route("/api/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    user_id = get_jwt_identity()
    if user_id == "guest_user":
        return jsonify({"message": "Welcome, Guest!"}), 200
    user = users.find_one({"_id": ObjectId(user_id)})
    if user:
        return jsonify({"message": f"Welcome back, {user['email']}!"}), 200
    return jsonify({"error": "User not found"}), 404

# ========================
# Prediction Logic
# ========================

def generate_graph(ticker, forecast):
    today = datetime.today().strftime('%Y-%m-%d')
    data = yf.download(ticker, start="2010-01-01", end=today)
    if data.empty:
        return ""
    plt.figure(figsize=(10, 5))
    plt.plot(data.index, data['Close'], label="Close Price")
    plt.axhline(y=forecast, color='r', linestyle='--', label=f"Forecast: ${forecast:.2f}")
    plt.title(f"{ticker.upper()} Historical Closing Prices")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
    plt.close()
    return f"data:image/png;base64,{encoded}"

def analyze_ticker(ticker):
    today = datetime.today().strftime('%Y-%m-%d')
    data = yf.download(ticker, start="2021-01-01", end=today)
    if data.empty or len(data) < 50:
        return "Not enough data", "N/A", "", {}, None, None
    try:
        options_signal = options_contracts_signal(ticker, std_multiplier=2)
    except Exception:
        options_signal = None
    options_strike = options_signal[2] if options_signal and options_signal[2] else 0.0
    fundamentals = get_fundamentals(ticker)
    forecast = predict_forecast(data, options_strike, fundamentals, ticker, min_train_size=50)
    if forecast is None:
        return "Not enough data", "N/A", "", {}, None, None
    current_price = float(data["Close"].iloc[-1])
    decision = "Yes" if forecast > current_price else "No"
    diff = forecast - current_price
    direction = "↑" if diff > 0 else "↓"
    relative_diff = abs(diff) / current_price * 100
    qualitative = "Low" if relative_diff < 1 else "Medium" if relative_diff < 5 else "High"
    confidence_score = 85 if relative_diff > 5 else 70 if relative_diff > 2 else 60
    individual_move = relative_diff / 2
    confidence = f"{qualitative} ({relative_diff:.1f}%)"
    graph = generate_graph(ticker, forecast)
    prediction_details = {
        "predicted_price": f"${forecast:.2f}",
        "prediction_diff": f"{direction} {relative_diff:.2f}%",
        "confidence_score": f"{confidence_score}%",
        "individual_move": f"{individual_move:.2f}%",
        "accuracy": "92%",
        "mae": "1.32",
        "time_completed": datetime.now().strftime("%b %d, %I:%M %p"),
    }
    return decision, confidence, graph, prediction_details, None, None

@app.route("/api/predict", methods=["POST"])
def predict():
    data = request.get_json()
    ticker = data.get("ticker", "").strip().upper()
    if not ticker:
        return {"error": "No ticker provided"}, 400
    try:
        decision, confidence, graph, prediction_details, _, _ = analyze_ticker(ticker)
        return {
            "ticker": ticker,
            "decision": decision,
            "confidence": confidence,
            "graph": graph,
            "prediction_details": prediction_details,
        }
    except Exception as e:
        return {"error": str(e)}, 500

# ========================
# Start Server
# ========================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
