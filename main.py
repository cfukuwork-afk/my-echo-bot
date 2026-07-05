import os
from fastapi import FastAPI, Request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from supabase import create_client
from openai import OpenAI
import asyncio

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 診断データを保持する辞書
# {user_id: {"step": 1, "answers": []}}
user_diagnoses = {}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: handler.handle(body.decode("utf-8"), signature))
    return {"status": "ok"}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text
    
    # 診断開始
    if text == "診断開始":
        user_diagnoses[user_id] = {"step": 1, "answers": []}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="【質問1/3】仕事で一番重視していることは？"))
        return

    # 診断中
    if user_id in user_diagnoses:
        d = user_diagnoses[user_id]
        d["answers"].append(text)
        
        if d["step"] < 3:
            d["step"] += 1
            questions = {2: "【質問2/3】チームでの自分の役割は？", 3: "【質問3/3】休日の過ごし方は？"}
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=questions[d["step"]]))
        else:
            # 3問終わったら判定
            prompt = f"以下の回答から性格タイプを1つ判定し、一言で表せ: {d['answers']}"
            ai_resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            personality = ai_resp.choices[0].message.content
            supabase.table("profiles").upsert({"user_id": user_id, "personality_type": personality}).execute()
            
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"診断完了！あなたのタイプは「{personality}」です。これからはこの性格を元に分析します。"))
            del user_diagnoses[user_id] # 診断終了
        return

    # 通常分析
    # (以下省略、先ほどと同じ)
