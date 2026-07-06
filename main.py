import os
from fastapi import FastAPI, Request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from supabase import create_client
from openai import OpenAI

# 初期化
app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# ※環境変数の SUPABASE_KEY は必ず「service_role」キーを設定してください
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 診断状態をメモリで管理
user_diagnoses = {}

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

    # 1. 診断開始コマンド
    if text == "診断開始":
        user_diagnoses[user_id] = {"step": 1, "answers": []}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="【1/3】仕事で何を重視しますか？"))
        return

    # 2. 診断中ロジック
    if user_id in user_diagnoses:
        d = user_diagnoses[user_id]
        d["answers"].append(text)
        
        if d["step"] == 1:
            d["step"] = 2
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="【2/3】チームでの役割は？"))
            return
        elif d["step"] == 2:
            d["step"] = 3
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="【3/3】休日の過ごし方は？"))
            return
        elif d["step"] == 3:
            # 診断終了と判定
            prompt = f"回答:{d['answers']}。この回答から性格タイプを1つ判定し、一言で結果を伝えて。"
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            personality = res.choices[0].message.content
            
            # logs テーブルに保存
            supabase.table("logs").insert({
                "user_id": user_id, 
                "message": "診断結果", 
                "ai_reply": personality
            }).execute()
            
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"診断完了！あなたのタイプは「{personality}」です。"))
            del user_diagnoses[user_id]
            return

    # 3. 通常分析（診断が完了している人向け）
    # 直近の ai_reply を取得
    res = supabase.table("logs").select("ai_reply").eq("user_id", user_id).order("id", desc=True).limit(1).execute()
    personality = res.data[0]['ai_reply'] if res.data else "未設定"
    
    prompt = f"専属コーチとして分析。性格:{personality}。入力:{text}。"
    ai_resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
    
    # ログを保存
    supabase.table("logs").insert({
        "user_id": user_id,
        "message": text,
        "ai_reply": ai_resp.choices[0].message.content
    }).execute()
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_resp.choices[0].message.content))
