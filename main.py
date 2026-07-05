import os
import logging
from fastapi import FastAPI, Request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from supabase import create_client
from openai import OpenAI
import asyncio

# ログ設定
logging.basicConfig(level=logging.INFO)

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

user_states = {}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    # 非同期でイベントをハンドリングするためにrun_in_executorを使います
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: handler.handle(body.decode("utf-8"), signature))
    return {"status": "ok"}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text

    if text == "診断開始":
        user_states[user_id] = "diagnosing"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="性格診断を開始します。最近の仕事で一番重視していることは何ですか？"))
        return

    if user_states.get(user_id) == "diagnosing":
        ai_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "回答から性格タイプを1つ判定せよ"},
                      {"role": "user", "content": text}]
        )
        personality = ai_resp.choices[0].message.content
        supabase.table("profiles").upsert({"user_id": user_id, "personality_type": personality}).execute()
        user_states[user_id] = "finished"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"診断完了！あなたのタイプは「{personality}」です。"))
        return

    # 通常の分析
    profile = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
    personality = profile.data[0]['personality_type'] if profile.data else "未設定"
    
    prompt = f"性格タイプ:{personality}。入力:{text}。分析とキーワードを1つ出力してください。"
    ai_resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    ai_reply = ai_resp.choices[0].message.content
    
    supabase.table("logs").insert({"user_id": user_id, "message": text, "ai_reply": ai_reply}).execute()
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
