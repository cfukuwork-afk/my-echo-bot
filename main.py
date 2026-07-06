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

# 診断状態（ユーザーIDごとに管理）
user_diagnoses = {}

# MBTI診断用質問リスト（100問）
QUESTIONS = [f"質問{i}: (MBTI診断用の質問{i}) 1:そう思う〜5:そう思わない" for i in range(1, 101)]

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
        user_diagnoses[user_id] = {"answers": []}
        # ご希望の文言で開始
        first_message = (
            "MBTI診断を開始します！\n"
            f"{QUESTIONS[0]}\n"
            "(回答を入力してください)"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=first_message))
        return

    # 2. 診断中ロジック（ユーザーの回答を待ってから次へ進む）
    if user_id in user_diagnoses:
        d = user_diagnoses[user_id]
        d["answers"].append(text)
        
        current_step = len(d["answers"])
        if current_step < 100:
            next_q = QUESTIONS[current_step]
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【{current_step + 1}/100】\n{next_q}"))
        else:
            # 100問終了後の分析処理
            line_bot_api.push_message(user_id, TextSendMessage(text="全100問終了！診断結果を分析しています..."))
            prompt = f"MBTI診断100問の回答データ:{d['answers']}。この回答から性格タイプ(MBTI)を判定し、専属コーチとして詳細な分析結果を一言で伝えて。"
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            result = res.choices[0].message.content
            
            # DBに診断結果を保存
            supabase.table("chat_logs").insert({
                "user_id": user_id, 
                "message": "診断結果", 
                "ai_reply": result
            }).execute()
            
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【診断結果】\n{result}"))
            del user_diagnoses[user_id]
        return

    # 3. 通常相談モード（診断開始以外の言葉が来た時）
    # 診断未実施者に案内を出し、診断済みにはコーチとして返答
    res = supabase.table("chat_logs").select("ai_reply").eq("user_id", user_id).order("id", desc=True).limit(1).execute()
    
    if not res.data:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="こんにちは！MBTI性格診断を始めるには「診断開始」と送ってください。"))
    else:
        profile = res.data[0]['ai_reply']
        ai_resp = client.chat.completions.create(model="gpt-4o", messages=[
            {"role": "system", "content": f"あなたはユーザーの専属コーチです。ユーザーの性格分析結果はこれです: {profile}。この結果に基づき、親身に相談に乗ってください。"},
            {"role": "user", "content": text}
        ])
        
        # 会話ログを保存
        supabase.table("chat_logs").insert({
            "user_id": user_id,
            "message": text,
            "ai_reply": ai_resp.choices[0].message.content
        }).execute()
        
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_resp.choices[0].message.content))
