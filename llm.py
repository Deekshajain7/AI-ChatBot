from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# ✅ Replace with your NewsAPI.org key
NEWS_API_KEY = "9830fcd69f284b8e8c0a093da8d165f8"
NEWS_API_BASE_URL = "https://newsapi.org/v2/everything"

def fetch_news(topic):
    if not topic:
        return {"error": "Topic is required."}
    
    # Calculate a date from the past (NewsAPI free tier has limitations on date range)
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    params = {
        "q": topic,
        "from": from_date,
        "sortBy": "publishedAt",
        "apiKey": NEWS_API_KEY,
        "language": "en",
        "pageSize": 5
    }
    
    try:
        response = requests.get(NEWS_API_BASE_URL, params=params)
        
        if response.status_code != 200:
            return {"error": f"Failed to fetch news from NewsAPI. Status: {response.status_code}"}
        
        data = response.json()
        
        # Check if there's an error in the API response
        if data.get("status") == "error":
            return {"error": f"API Error: {data.get('message', 'Unknown error')}"}
        
        articles = data.get("articles", [])
        
        if not articles:
            return {"message": f"No news found for '{topic}'."}
        
        return {
            "news": [
                {
                    "title": article["title"], 
                    "description": article["description"],
                    "url": article["url"],
                    "publishedAt": article["publishedAt"]
                }
                for article in articles
            ]
        }
    
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

@app.route("/api/current_affairs", methods=["GET"])
def get_news_by_topic():
    topic = request.args.get("topic", "").strip()
    
    if not topic:
        return jsonify({"error": "Topic parameter is required"}), 400
    
    result = fetch_news(topic)
    
    if "error" in result:
        status = 400
    elif "message" in result:
        status = 404
    else:
        status = 200
    
    return jsonify(result), status

# Add a test route to check if the API is working
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "News API is running!",
        "usage": "Use /api/current_affairs?topic=your_topic_here",
        "example": "/api/current_affairs?topic=tesla"
    })

if __name__ == "__main__":
    app.run(port=5000, debug=True)