from flask import Flask, render_template, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import random
import datetime
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "your_secret_key_2025"

# 配置 SQLite 数据库
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///guess_game.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # 会话有效期

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 定义成绩模型 - 增强版
class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_name = db.Column(db.String(50), nullable=False, default="匿名玩家")
    tries = db.Column(db.Integer, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False, default="normal")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    game_time = db.Column(db.Float, default=0.0)  # 游戏时长(秒)

    def to_dict(self):
        return {
            "id": self.id,
            "player_name": self.player_name or "未知玩家",
            "tries": self.tries if self.tries is not None else -1,
            "difficulty": self.difficulty or "未知难度",
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else "未知时间",
            "game_time": f"{self.game_time:.1f}秒" if self.game_time is not None else "未知时间"
        }

# 创建数据库表
with app.app_context():
    db.create_all()

# 游戏配置
DIFFICULTY_SETTINGS = {
    "easy": {"min": 1, "max": 50, "max_tries": 10},
    "normal": {"min": 1, "max": 100, "max_tries": 8},
    "hard": {"min": 1, "max": 200, "max_tries": 6},
    "expert": {"min": 1, "max": 500, "max_tries": 5}
}

@app.route("/", methods=["GET", "POST"])
def index():
    # 初始化玩家名称
    if "player_name" not in session:
        session["player_name"] = "玩家" + str(random.randint(1000, 9999))
    
    # 初始化游戏难度
    if "difficulty" not in session:
        session["difficulty"] = "normal"
    
    # 处理设置玩家名称
    if request.method == "POST" and "set_name" in request.form:
        new_name = request.form.get("player_name", "").strip()
        if new_name:
            session["player_name"] = new_name
        return redirect(url_for("index"))
    
    # 处理难度选择
    if request.method == "POST" and "set_difficulty" in request.form:
        difficulty = request.form.get("difficulty", "normal")
        if difficulty in DIFFICULTY_SETTINGS:
            session["difficulty"] = difficulty
            # 重置当前游戏
            if "secret_number" in session:
                session.pop("secret_number")
                session.pop("tries")
                session.pop("start_time")
                session.pop("history")
        return redirect(url_for("index"))
    
    # 初始化新游戏
    if "secret_number" not in session:
        settings = DIFFICULTY_SETTINGS[session["difficulty"]]
        session["secret_number"] = random.randint(settings["min"], settings["max"])
        session["tries"] = 0
        session["start_time"] = datetime.datetime.now().timestamp()
        session["history"] = []
        session["game_active"] = True
    
    # 处理游戏逻辑
    message = ""
    hint = ""
    game_won = False
    
    if request.method == "POST" and "guess" in request.form and session["game_active"]:
        try:
            guess = int(request.form["guess"])
            settings = DIFFICULTY_SETTINGS[session["difficulty"]]
            
            if guess < settings["min"] or guess > settings["max"]:
                message = f"请输入 {settings['min']} 到 {settings['max']} 之间的数字！"
            else:
                session["tries"] += 1
                session.modified = True
                
                # 记录历史尝试
                history_entry = {
                    "guess": guess,
                    "result": "",
                    "try_num": session["tries"]
                }
                
                if guess < session["secret_number"]:
                    message = "太小了！"
                    hint = f"提示：大于 {guess}"
                    history_entry["result"] = "low"
                elif guess > session["secret_number"]:
                    message = "太大了！"
                    hint = f"提示：小于 {guess}"
                    history_entry["result"] = "high"
                else:
                    # 游戏胜利
                    game_won = True
                    session["game_active"] = False
                    end_time = datetime.datetime.now().timestamp()
                    game_time = end_time - session["start_time"]
                    
                    message = f"🎉 恭喜 {session['player_name']} 猜对了！数字是 {session['secret_number']}！"
                    message += f"<br>你总共猜了 {session['tries']} 次，用时 {game_time:.1f} 秒！"
                    
                    # 保存成绩到数据库
                    new_score = Score(
                        player_name=session["player_name"],
                        tries=session["tries"],
                        difficulty=session["difficulty"],
                        game_time=game_time
                    )
                    db.session.add(new_score)
                    db.session.commit()
                    
                    history_entry["result"] = "correct"
                
                # 添加历史记录
                session["history"].insert(0, history_entry)
                
                # 检查尝试次数限制
                if not game_won and session["tries"] >= settings["max_tries"]:
                    session["game_active"] = False
                    message = f"游戏结束！你没有在 {settings['max_tries']} 次内猜出数字。"
                    message += f"<br>正确答案是：{session['secret_number']}"
        
        except ValueError:
            message = "请输入有效数字！"
    
    # 处理重置游戏
    if request.method == "POST" and "reset" in request.form:
        session.pop("secret_number", None)
        session.pop("tries", None)
        session.pop("start_time", None)
        session.pop("history", None)
        session.pop("game_active", None)
        return redirect(url_for("index"))
    
    # 获取排行榜数据
    top_scores = Score.query.order_by(Score.tries, Score.game_time).limit(10).all()
    top_scores = [score.to_dict() for score in top_scores]
    
    # 获取当前游戏状态
    game_settings = DIFFICULTY_SETTINGS[session["difficulty"]]
    
    return render_template(
        "index.html",
        player_name=session["player_name"],
        difficulty=session["difficulty"],
        difficulties=list(DIFFICULTY_SETTINGS.keys()),
        tries=session.get("tries", 0),
        max_tries=game_settings["max_tries"],
        min_num=game_settings["min"],
        max_num=game_settings["max"],
        message=message,
        hint=hint,
        game_active=session.get("game_active", False),
        history=session.get("history", []),
        top_scores=top_scores,
        game_won=game_won
    )

if __name__ == "__main__":
    app.run(debug=True)