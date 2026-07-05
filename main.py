import os
import logging
from fastapi import FastAPI, Request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from openai import OpenAI

# ログ設定
logging.basicConfig(level=logging.INFO)

# 各種設定
app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    handler.handle(body.decode("utf-8"), signature)
    return {"status": "ok"}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    
    # AI分析
    prompt = f"以下の入力を分析し、洞察と今日のキーワードを1つ出力してください: {user_text}"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "あなたは分析のプロです。"},
                  {"role": "user", "content": prompt}]
    )
    
    ai_reply = response.choices[0].message.content
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
