import os
from fastapi import FastAPI, Request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from supabase import create_client
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 簡易的な診断状態管理（本来はDBで管理すべきですが、まずはこれで）
user_states = {} 

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    handler.handle(body.decode("utf-8"), signature)
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
        # 診断結果の決定と保存
        ai_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "回答から性格タイプ(例: 論理型)を1つ判定せよ"},
                      {"role": "user", "content": text}]
        )
        personality = ai_resp.choices[0].message.content
        
        # Supabaseに保存
        supabase.table("profiles").upsert({"user_id": user_id, "personality_type": personality}).execute()
        
        user_states[user_id] = "finished"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"診断完了！あなたのタイプは「{personality}」です。これからはこの性格を元に分析します。"))
        return

    # 通常の分析モード
    # (先ほどの分析ロジックをここに続ける)
