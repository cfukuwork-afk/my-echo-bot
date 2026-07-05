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

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    handler.handle(body.decode("utf-8"), signature)
    return {"status": "ok"}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text
    
    # 1. 性格データの取得
    profile = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
    personality = profile.data[0]['personality_type'] if profile.data else "未設定"
    
    # 2. AI分析（性格データ付き）
    prompt = f"あなたは私の専属コーチです。性格タイプ:{personality}。入力:{user_text}。分析とキーワードをください。"
    ai_resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    ai_reply = ai_resp.choices[0].message.content
    
    # 3. ログの保存
    supabase.table("logs").insert({"user_id": user_id, "message": user_text, "ai_reply": ai_reply}).execute()
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
