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

user_diagnoses = {}

# 統計分析用のMBTI100問リスト
QUESTIONS = [
    "1. 人と過ごすとエネルギーが満たされる。", "2. 自分の考えを言葉にする前に頭の中で整理したい。", "3. 論理よりも感情を重視する。", "4. 締め切り直前に集中して作業する。", "5. 現実より理想的な未来を考えるのが好きだ。",
    "6. 事実よりも感情で判断することが多い。", "7. その場の状況で柔軟に計画を変える。", "8. 他人の評価より自分の納得感を優先する。", "9. 抽象的議論より具体的な話が好きだ。", "10. 周囲に意見を合わせることが多い。",
    "11. 社交的な集まりは楽しい。", "12. 一人でいる時間が長く必要だ。", "13. 困っている人はすぐに助けたい。", "14. 細かい計画より大まかな方針が重要だ。", "15. 自分の直感を信じる。", "16. 感情的になりやすい。", "17. 常に新しいことに挑戦したい。", "18. 他人をリーダーシップで導くのは得意だ。", "19. データや分析を重視する。", "20. 変化よりも安定が好きだ。",
    "21. 知らない人にも話しかけられる。", "22. 静かな場所で落ち着きたい。", "23. 議論では相手の感情を傷つけたくない。", "24. 物事は期限ギリギリの方が効率的だ。", "25. 目に見えることしか信じない。", "26. 冷静な客観的事実が重要だ。", "27. ルールは柔軟に解釈すべきだ。", "28. 自分の価値観を大切にする。", "29. 理論的な仮説を考えるのが好きだ。", "30. 誰かと一緒にいると安心する。",
    "31. 注目を集めるのは嫌いではない。", "32. 一人で深く考え込む癖がある。", "33. 人の気持ちを察するのは得意だ。", "34. 計画通りに進まないとイライラする。", "35. 過去の経験から学ぼうとする。", "36. 自分の成功よりもチームの調和が大事だ。", "37. 衝動的に行動することがある。", "38. 人と協力するより一人で作業したい。", "39. 問題の全体像を把握したい。", "40. 自分の感情を抑えるのは簡単だ。",
    "41. パーティーでは盛り上げ役に回る。", "42. 読書や趣味は一人で楽しみたい。", "43. 誰かが悲しんでいると自分も辛い。", "44. 締め切りを守ることは絶対だ。", "45. 新しい可能性を探るのが好きだ。", "46. 論理的矛盾はすぐに指摘する。", "47. 準備万端でないと不安だ。", "48. 他人の目線が気になる。", "49. 複雑な仕組みを理解するのが好きだ。", "50. 初対面でもすぐ打ち解けられる。",
    "51. 議論には積極的に参加する。", "52. 人混みに行くと疲れてしまう。", "53. 人に好かれることが重要だ。", "54. 直前にならないとエンジンがかからない。", "55. 具体的なデータが信頼できる。", "56. 感情に流されず決断できる。", "57. その日の気分で予定を変える。", "58. 自分の信念は曲げない。", "59. 将来のビジョンを想像するのが好きだ。", "60. 人と話すと考えがまとまる。",
    "61. 大人数での活動を好む。", "62. 一人で静かに考えたい。", "63. 厳しいことでもはっきり伝える。", "64. スケジュール帳を常に持ち歩く。", "65. 直感的に良いか悪いか分かる。", "66. 感受性が豊かである。", "67. ルーチンワークは退屈だ。", "68. 自分の個性を大事にしたい。", "69. 学問的な好奇心が強い。", "70. 賑やかな場所が好きだ。",
    "71. 自分の意見を言うのが得意だ。", "72. 一人で行動するのが楽だ。", "73. 相手の立場になって考えられる。", "74. 整理整頓は完璧にしたい。", "75. 現状よりも未来の可能性に興味がある。", "76. 正確さを何よりも重視する。", "77. 計画に縛られるのは苦手だ。", "78. 他人の期待に応えたい。", "79. なぜそうなるのか仕組みを知りたい。", "80. 初めて会う人にも興味がある。",
    "81. 会話の中心にいるのが好きだ。", "82. 自分の内面世界が充実している。", "83. 人に感謝されると嬉しい。", "84. 忘れ物をしないよう確認する。", "85. 現実的な解決策を考える。", "86. 感情よりも理屈で物事を片付ける。", "87. 予定外の出来事を楽しめる。", "88. 自分のやり方を貫く。", "89. アイデアを膨らませるのが好きだ。", "90. 一人でいるときが一番落ち着く。",
    "91. 誰とでもすぐに仲良くなれる。", "92. 自分の考えを大切にしたい。", "93. 争いごとは避けたい。", "94. 計画を立てるプロセスが好きだ。", "95. 創造的な仕事に興味がある。", "96. 感情で判断する人を見ると呆れる。", "97. 臨機応変に対応するのが得意だ。", "98. 他人の意見を尊重する。", "99. 分析的に物事を考えるのが好きだ。", "100. 毎日の生活を計画的に送りたい。"
]

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
    
    if text == "占い":
        # 占いロジック
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="今日のラッキーカラーは青です。"))
        return

    if text == "診断開始":
        user_diagnoses[user_id] = {"answers": []}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"【MBTI 100問診断：開始】\n{QUESTIONS[0]}\n(1〜5で答えてね)"))
        return

    if user_id in user_diagnoses:
        d = user_diagnoses[user_id]
        d["answers"].append(text)
        current_idx = len(d["answers"])
        
        if current_idx < 100:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"【{current_idx+1}/100】\n{QUESTIONS[current_idx]}"))
        else:
            # 分析
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="全100問終了！分析中..."))
            prompt = f"100個の回答:{d['answers']}。この統計データから正確なMBTIタイプを特定し、性格特性をコーチとして分析せよ。"
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            analysis = res.choices[0].message.content
            supabase.table("logs").insert({"user_id": user_id, "message": "診断結果", "ai_reply": analysis}).execute()
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【診断結果】\n{analysis}"))
            del user_diagnoses[user_id]
        return

    # 通常相談
    res = supabase.table("logs").select("ai_reply").eq("user_id", user_id).order("id", desc=True).limit(1).execute()
    profile = res.data[0]['ai_reply'] if res.data else "未診断"
    ai_resp = client.chat.completions.create(model="gpt-4o", messages=[
        {"role": "system", "content": f"専属コーチ。性格:{profile}。相談に乗れ。"},
        {"role": "user", "content": text}
    ])
    supabase.table("logs").insert({"user_id": user_id, "message": text, "ai_reply": ai_resp.choices[0].message.content}).execute()
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_resp.choices[0].message.content))
