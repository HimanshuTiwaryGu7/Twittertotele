import os
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import tweepy
import requests
from io import BytesIO
from flask import Flask
import threading

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Credentials
TWITTER_API_KEY = 'MroH2zmSzO8N1LsawRVT8feMU'
TWITTER_API_SECRET = 'M3q2WDa2qBVklxHXyiCorHJq7mpBtd9G82yP95SQjnXdqmAoJa'
TWITTER_ACCESS_TOKEN = '1880993642929893376-lDwFQN273VAeMpKFwM76UyhlXyMbwa'
TWITTER_ACCESS_SECRET = '3LZDvID0q4UMCwDcFgOVEKKR6u564hEe3PTcxZulEJ3FN'
TELEGRAM_BOT_TOKEN = '7999623146:AAGCCC_FwridGlPskLXUP1TLQg5RiwVUezU'

# Twitter API v2 setup with OAuth 1.0a User Context
try:
    client = tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_SECRET,
        wait_on_rate_limit=True
    )
    
    # Keep v1.1 API for media upload only
    auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
    twitter_api = tweepy.API(auth)
    logger.info("Twitter API authentication successful")
except Exception as e:
    logger.error(f"Failed to initialize Twitter API: {str(e)}")
    raise

def start(update, context):
    """Send a message when the command /start is issued."""
    welcome_message = (
        "👋 Hello! I'm a Telegram-to-Twitter bot.\n\n"
        "Add me to your channel as an admin and I will automatically:\n"
        "✅ Post text messages to Twitter\n"
        "📸 Upload photos with captions\n"
        "🎥 Share videos with descriptions\n\n"
        "Make sure I have admin rights in your channel!"
    )
    update.message.reply_text(welcome_message)

def handle_text(update, context):
    """Handle text messages"""
    try:
        # Check if message contains 🚨 symbol
        if '🚨' in update.channel_post.text:
            response = client.create_tweet(text=update.channel_post.text)
            logging.info("Text posted to Twitter successfully")
        else:
            logging.info("Message skipped - no 🚨 symbol found")
    except Exception as e:
        logging.error(f"Error posting text to Twitter: {str(e)}")
        if "403" in str(e):
            logging.error("Twitter API access level insufficient. Please upgrade your API access.")

def handle_photo(update, context):
    """Handle photo messages"""
    try:
        # Get the largest photo
        photo = update.channel_post.photo[-1]
        
        # Get photo file
        photo_file = context.bot.get_file(photo.file_id)
        
        # Download photo
        response = requests.get(photo_file.file_path)
        
        # Upload media using v1.1 API
        media = twitter_api.media_upload(filename="photo.jpg", file=BytesIO(response.content))
        
        # Create tweet with media using v2 API
        response = client.create_tweet(
            text=update.channel_post.caption if update.channel_post.caption else "",
            media_ids=[media.media_id]
        )
        logging.info("Photo posted to Twitter successfully")
    except Exception as e:
        logging.error(f"Error posting photo to Twitter: {str(e)}")
        if "403" in str(e):
            logging.error("Twitter API access level insufficient. Please upgrade your API access.")

def handle_video(update, context):
    """Handle video messages"""
    try:
        # Get video file
        video_file = context.bot.get_file(update.channel_post.video.file_id)
        
        # Download video
        response = requests.get(video_file.file_path)
        
        # Save video temporarily
        with open("temp_video.mp4", "wb") as f:
            f.write(response.content)
        
        # Upload media using v1.1 API
        media = twitter_api.media_upload(
            filename="video.mp4",
            file="temp_video.mp4",
            media_category="tweet_video"
        )
        
        # Create tweet with media using v2 API
        response = client.create_tweet(
            text=update.channel_post.caption if update.channel_post.caption else "",
            media_ids=[media.media_id]
        )
        
        # Clean up temporary file
        os.remove("temp_video.mp4")
        logging.info("Video posted to Twitter successfully")
    except Exception as e:
        logging.error(f"Error posting video to Twitter: {str(e)}")
        if "403" in str(e):
            logging.error("Twitter API access level insufficient. Please upgrade your API access.")

def handle_channel_post(update, context):
    """Main handler for channel posts"""
    try:
        if update.channel_post.text and not update.channel_post.photo:
            handle_text(update, context)
        elif update.channel_post.photo:
            handle_photo(update, context)
        elif update.channel_post.video:
            handle_video(update, context)
    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")

# Initialize Flask app
app = Flask(__name__)

@app.route('/')
@app.route('/health')
def health_check():
    return 'Bot is running!', 200

def run_flask():
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)

def main():
    """Start the bot"""
    try:
        # Create updater and pass in bot token
        updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
        logger.info("Telegram bot initialized successfully")

        # Get the dispatcher to register handlers
        dp = updater.dispatcher

        # Add command handlers
        dp.add_handler(CommandHandler("start", start))

        # Add handler for channel posts
        dp.add_handler(MessageHandler(Filters.update.channel_posts, handle_channel_post))

        # Start Flask in a separate thread
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()

        # Start the bot
        updater.start_polling()
        
        # Run the bot until you press Ctrl-C
        updater.idle()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        raise

if __name__ == '__main__':
    main()
