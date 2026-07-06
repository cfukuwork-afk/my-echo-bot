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

# 診断状態（step: 何問目か, answers: 回答リスト）
user_diagnoses = {}

# 100問の質問リスト（簡易版として配列を用意）
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

    if text == "診断開始":
        user_diagnoses[user_id] = {"step": 0, "answers": []}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"MBTI診断を開始します！\n{QUESTIONS[0]}\n(回答を入力してください)"))
        return

    if user_id in user_diagnoses:
        d = user_diagnoses[user_id]
        d["answers"].append(text)
        
# 修正箇所: 100問ロジックの中
        if len(d["answers"]) < 100:
            next_q = QUESTIONS[len(d["answers"])]
            # reply_message を push_message に変更
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【{len(d['answers'])}/100】\n{next_q}"))
        else:
            # 100問終了！AIによる分析
            line_bot_api.push_message(user_id, TextSendMessage(text="診断終了！分析しています..."))            
            prompt = f"MBTI診断100問の回答:{d['answers']}。あなたのタイプを分析し、専属コーチとして性格特性を詳細に教えて。"
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            result = res.choices[0].message.content
            
            supabase.table("chat_logs").insert({"user_id": user_id, "message": "診断結果", "ai_reply": result}).execute()
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【診断結果】\n{result}"))
            del user_diagnoses[user_id]
        return

    # 通常相談モード（診断完了後）
    res = supabase.table("chat_logs").select("ai_reply").eq("user_id", user_id).order("id", desc=True).limit(1).execute()
    profile = res.data[0]['ai_reply'] if res.data else "未診断"
    ai_resp = client.chat.completions.create(model="gpt-4o", messages=[
        {"role": "system", "content": f"あなたはユーザーの専属コーチです。ユーザーのMBTI分析結果はこれです: {profile}"},
        {"role": "user", "content": text}
    ])
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_resp.choices[0].message.content))
