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

# 心理統計学に基づいた100問の質問リスト
QUESTIONS = [
    "1. 人と過ごした後よりも、一人で過ごした後の方が元気が回復する。", "2. 自分の考えを言葉にする前に、頭の中でじっくり整理したい。", "3. 論理よりも感情を重視する。", "4. 締め切り直前になってから集中して作業を始める。", "5. 現実的なことよりも、理想や未来のアイデアに興味がある。",
    "6. 事実よりも感情で判断することが多い。", "7. 計画を立てるよりも、その場の状況に合わせて動くのが好きだ。", "8. 他人の評価より、自分の納得感を最優先する。", "9. 抽象的な議論よりも、具体的な事実や詳細の話が好きだ。", "10. 周囲の雰囲気に合わせて自分の意見を調整することがある。",
    "11. 大勢の集まりに行くとエネルギーが満たされる。", "12. 静かな場所で一人の時間を過ごすのが必要不可欠だ。", "13. 困っている人がいたら、たとえ忙しくても助けたい。", "14. 細かい計画より、大まかな方針を決めて進むのが良い。", "15. 自分の直感を信じて行動することが多い。", "16. 感情的になりやすく、表情にも出やすい。", "17. 常に新しい挑戦をして変化を楽しみたい。", "18. 人を導くリーダーシップを発揮するのは得意だ。", "19. 直感よりもデータや分析に基づいた判断を好む。", "20. 変化よりも安定した環境で仕事をしたい。",
    "21. 初対面の人にも自分から話しかけることができる。", "22. 静かな環境で深く考え込む時間が好きだ。", "23. 相手の感情を傷つけないよう、議論では言葉を選ぶ。", "24. 物事は期限ギリギリにやるほうが効率が上がる。", "25. 目に見える具体的な物事を信じる傾向がある。", "26. 冷静で客観的な事実に基づいて意思決定する。", "27. ルールは状況に応じて柔軟に解釈すべきだ。", "28. 自分の信念を貫き、他人には流されない。", "29. 理論的な仮説を立てたり、議論するのが楽しい。", "30. 誰かと一緒にいると安心感を感じる。",
    "31. 注目を集めるのは嫌いではなく、むしろ心地よい。", "32. 一人で深く考え込み、内省する癖がある。", "33. 他人の感情を察して共感するのは得意だ。", "34. 計画通りに進まないと強いストレスを感じる。", "35. 過去の経験から学び、それを次に活かす。", "36. 自分の成功よりも、チームの調和を重視する。", "37. 計画を立てずに衝動的に行動することがある。", "38. 人と協力するよりも、一人で黙々と作業したい。", "39. 物事の細部よりも、問題の全体像を把握したい。", "40. 自分の感情をコントロールして抑えるのは簡単だ。",
    "41. パーティー等では、自分が盛り上げ役に回るほうだ。", "42. 読書や趣味は一人で楽しむのが一番いい。", "43. 誰かが悲しんでいると、自分もつらくなってくる。", "44. 締め切りを守ることは、何よりも絶対的だ。", "45. 目の前のことより、新しい可能性を探るのが好きだ。", "46. 論理的矛盾にはすぐに気づき、指摘したくなる。", "47. 準備万端でないと、不安で何も手につかない。", "48. 他人からどう思われているかが気になってしまう。", "49. 複雑な仕組みを理解し、整理するのが楽しい。", "50. 初対面でもすぐに打ち解けて話せる。",
    "51. 議論や意見交換には積極的に参加する。", "52. 人混みに行くと消耗して疲れてしまう。", "53. 人に好かれることは、自分にとって非常に重要だ。", "54. 直前にならないと、なかなかエンジンがかからない。", "55. 直感より具体的なデータや証拠を信頼する。", "56. 感情に流されず、ドライに決断を下せる。", "57. その日の気分や状況で、予定をすぐに変える。", "58. 自分の価値観は、どんな状況でも曲げない。", "59. 将来の壮大なビジョンを想像するのが好きだ。", "60. 人と話すことで、自分の考えがまとまる。",
    "61. 大人数での活動やイベントを好む。", "62. 一人で静かに考え、自分と向き合いたい。", "63. 厳しいことでも、必要ならはっきり伝える。", "64. スケジュール帳を常に確認し、管理している。", "65. 直感的に「これは良い/悪い」と感じることが多い。", "66. 感受性が豊かで、細かい変化に気づきやすい。", "67. ルーチンワークを毎日繰り返すのは退屈だ。", "68. 自分の個性を大事にし、誰とも違う自分でありたい。", "69. 学問的な好奇心が強く、知識欲が旺盛だ。", "70. 賑やかな場所の方が、落ち着いていられる。",
    "71. 自分の意見をはっきり言うのが得意だ。", "72. 誰かと行動するより、一人で行動するほうが楽だ。", "73. 相手の立場になって物事を考えることができる。", "74. 部屋の整理整頓は完璧にしておきたい。", "75. 現状維持より、未来の可能性に興味がある。", "76. 正確さと論理的な正しさを何よりも重視する。", "77. 計画に縛られると息苦しく、苦手だ。", "78. 他人の期待に応えることに喜びを感じる。", "79. なぜそうなるのか、仕組みや原理を知りたい。", "80. 初めて会う人にも興味を持ち、知ろうとする。",
    "81. 会話の中心にいるのが好きで、沈黙が苦手だ。", "82. 自分の内面世界が充実しており、退屈しない。", "83. 人から感謝されると、非常に達成感を感じる。", "84. 忘れ物をしないよう、何度も確認して管理する。", "85. 現実的で地に足のついた解決策を考える。", "86. 感情よりも理屈で物事を片付けるほうが楽だ。", "87. 予定外の出来事や変化を楽しめる。", "88. 他人にどう思われようと、自分のやり方を貫く。", "89. アイデアを広げていくのが好きだ。", "90. 一人でいるときが、最も自分らしくいられる。",
    "91. 誰とでもすぐに仲良くなれる自信がある。", "92. 自分の考えを大切にしたいので、一人になりたい。", "93. 争いごとは避け、穏便に済ませたい。", "94. 計画を立てて着実に進むプロセスが好きだ。", "95. 創造的な仕事や、ゼロから何かを生み出すことが好き。", "96. 感情で判断する人を見ると、論理的でないと感じる。", "97. 突発的なトラブルも臨機応変に対応するのが得意だ。", "98. 他人の意見を尊重し、耳を傾けるようにしている。", "99. 分析的に物事を考えるのが好きだ。", "100. 毎日の生活を計画的に送ることに充実感がある。"
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
    
    if text == "診断開始":
        supabase.table("diagnoses").upsert({"user_id": user_id, "answers": []}).execute()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"【1/100】\n{QUESTIONS[0]}\n(1〜5で回答)"))
        return

    res = supabase.table("diagnoses").select("answers").eq("user_id", user_id).execute()
    if res.data:
        answers = res.data[0]["answers"]
        answers.append(text)
        supabase.table("diagnoses").update({"answers": answers}).eq("user_id", user_id).execute()
        
        if len(answers) < 100:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"【{len(answers)+1}/100】\n{QUESTIONS[len(answers)]}"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="全100問完了！分析中..."))
            prompt = f"100問の回答:{answers}。この統計データに基づき、あなたのMBTIタイプと性格分析をコーチとして詳細に伝えて。"
            analysis = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
            supabase.table("logs").insert({"user_id": user_id, "message": "診断結果", "ai_reply": analysis}).execute()
            line_bot_api.push_message(user_id, TextSendMessage(text=f"【診断完了！】\n{analysis}"))
            supabase.table("diagnoses").delete().eq("user_id", user_id).execute()
        return

    # 通常コーチモード
    res_log = supabase.table("logs").select("ai_reply").eq("user_id", user_id).order("id", desc=True).limit(1).execute()
    profile = res_log.data[0]['ai_reply'] if res_log.data else "未診断"
    ai_resp = client.chat.completions.create(model="gpt-4o", messages=[
        {"role": "system", "content": f"あなたは専属コーチ。性格:{profile}。相談に乗れ。"},
        {"role": "user", "content": text}
    ])
    supabase.table("logs").insert({"user_id": user_id, "message": text, "ai_reply": ai_resp.choices[0].message.content}).execute()
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_resp.choices[0].message.content))
