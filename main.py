import os
import logging
from fastapi import FastAPI, Request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from openai import OpenAI

# ログの設定
logging.basicConfig(level=logging.INFO)

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    # イベントを処理
    handler.handle(body.decode("utf-8"), signature)
    return {"status": "ok"}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # reply_tokenは一度しか使えないため、エラー回避のためのチェックを行う
    try:
        user_text = event.message.text
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたはユーザーの思考の癖を分析するAIです。短く、洞察に満ちた返答をしてください。"},
                {"role": "user", "content": user_text}
            ]
        )
        ai_reply = response.choices[0].message.content
        
        # 返信実行
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
        
    except Exception as e:
        # 既に使われたトークンなどのエラーはログに出すだけで停止させない
        logging.error(f"Error occurred: {e}")
