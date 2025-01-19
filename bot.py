import os
import logging
from dotenv import load_dotenv
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import tweepy
import requests
from io import BytesIO
from aiohttp import web
import asyncio

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Twitter API v2 setup with OAuth 1.0a User Context
client = tweepy.Client(
    consumer_key=os.getenv('TWITTER_API_KEY'),
    consumer_secret=os.getenv('TWITTER_API_SECRET'),
    access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
    access_token_secret=os.getenv('TWITTER_ACCESS_SECRET'),
    wait_on_rate_limit=True
)

# Keep v1.1 API for media upload only
auth = tweepy.OAuthHandler(
    os.getenv('TWITTER_API_KEY'),
    os.getenv('TWITTER_API_SECRET')
)
auth.set_access_token(
    os.getenv('TWITTER_ACCESS_TOKEN'),
    os.getenv('TWITTER_ACCESS_SECRET')
)
twitter_api = tweepy.API(auth)

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

async def web_server():
    app = web.Application()
    
    async def health_check(request):
        return web.Response(text="Bot is running!", status=200)
    
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")
    return runner

async def run_bot():
    """Start the bot"""
    updater = Updater(os.getenv('TELEGRAM_BOT_TOKEN'), use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.update.channel_posts, handle_channel_post))
    updater.start_polling()
    print("Bot started!")
    await asyncio.sleep(float('inf'))

async def main():
    try:
        # Start web server first
        runner = await web_server()
        # Start bot
        await run_bot()
    except KeyboardInterrupt:
        print("Bot stopped!")

if __name__ == '__main__':
    asyncio.run(main())
