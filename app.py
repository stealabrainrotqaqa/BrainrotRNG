import os
import random
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gizli-anahtar-123456'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Float, nullable=False)

class UserInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Integer, default=1)

class TradeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(150), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Integer, default=1)
    type = db.Column(db.String(20), default="DEPOSIT")
    status = db.Column(db.String(50), default="Bekliyor")
    messages = db.relationship('ChatMessage', backref='trade', cascade="all, delete-orphan")

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trade_id = db.Column(db.Integer, db.ForeignKey('trade_request.id'), nullable=False)
    sender_username = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(500), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 📌 VERİTABANI BAŞLANGIÇ OTOMATİK KURULUMU (Gunicorn için buraya alındı)
with app.app_context():
    db.create_all()
    if not Stock.query.first():
        default_stocks = [
            ("Dragon Cannelloni", 1.00),
            ("Capitano Moby", 0.17),
            ("Garama", 0.06),
            ("Cash or Card", 0.08),
            ("Cerberus", 0.24)
        ]
        for name, val in default_stocks:
            db.session.add(Stock(name=name, value=val))
        db.session.commit()

@app.route('/')
@login_required
def index():
    stocks = Stock.query.all()
    all_values = {s.name: s.value for s in stocks}
    user_items = UserInventory.query.filter_by(user_id=current_user.id).all()
    my_requests = TradeRequest.query.filter_by(user_id=current_user.id).order_by(TradeRequest.id.desc()).all()
    return render_template('index.html', user_items=user_items, all_values=all_values, stocks=stocks, my_requests=my_requests)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Hatalı kullanıcı adı veya şifre!', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        raw_password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten kullanılıyor.', 'danger')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(raw_password)
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if current_user.username != 'RealSaatYilmaz':
        flash('Bu sayfaya sadece RealSaatYilmaz erişebilir!', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_stock':
            name = request.form.get('name')
            try:
                value = float(request.form.get('value', 0))
            except ValueError:
                value = 0.0
            if Stock.query.filter_by(name=name).first():
                flash('Bu brainrot zaten stokta var!', 'warning')
            else:
                db.session.add(Stock(name=name, value=value))
                db.session.commit()
                flash(f'{name} stoğa eklendi.', 'success')
        elif action == 'delete_stock':
            stock = Stock.query.get(request.form.get('stock_id'))
            if stock:
                db.session.delete(stock)
                db.session.commit()
                flash('Stok silindi!', 'info')
        elif action in ['approve_trade', 'reject_trade']:
            trade = TradeRequest.query.get(request.form.get('trade_id'))
            if trade and trade.status == "Bekliyor":
                if action == 'approve_trade':
                    trade.status = "Onaylandı / Teslim Edildi"
                    if trade.type == "DEPOSIT":
                        inv = UserInventory.query.filter_by(user_id=trade.user_id, item_name=trade.item_name).first()
                        if inv:
                            inv.amount += trade.amount
                        else:
                            db.session.add(UserInventory(user_id=trade.user_id, item_name=trade.item_name, amount=trade.amount))
                    db.session.commit()
                    flash('Talep onaylandı!', 'success')
                elif action == 'reject_trade':
                    trade.status = "Reddedildi"
                    db.session.commit()
                    flash('Talep reddedildi.', 'danger')

    stocks = Stock.query.all()
    deposits = TradeRequest.query.filter_by(type="DEPOSIT", status="Bekliyor").all()
    wins = TradeRequest.query.filter_by(type="WIN", status="Bekliyor").all()
    return render_template('admin.html', stocks=stocks, deposits=deposits, wins=wins)

@app.route('/deposit', methods=['POST'])
@login_required
def deposit():
    item_name = request.form.get('item_name')
    try:
        amount = int(request.form.get('amount', 1))
    except ValueError:
        amount = 1

    if not Stock.query.filter_by(name=item_name).first():
        flash('Geçersiz eşya!', 'danger')
        return redirect(url_for('index'))
        
    new_trade = TradeRequest(user_id=current_user.id, username=current_user.username, item_name=item_name, amount=amount, type="DEPOSIT", status="Bekliyor")
    db.session.add(new_trade)
    db.session.commit()
    
    db.session.add(ChatMessage(trade_id=new_trade.id, sender_username="Sistem", message=f"{current_user.username} yatırma talebi oluşturdu."))
    db.session.commit()
    flash('Yatırma talebi oluşturuldu.', 'info')
    return redirect(url_for('index'))

@app.route('/rng', methods=['POST'])
@login_required
def rng():
    item_name = request.form.get('item_name')
    inv_item = UserInventory.query.filter_by(user_id=current_user.id, item_name=item_name).first()
    if not inv_item or inv_item.amount < 1:
        return {"status": "error", "message": "Yetersiz envanter!"}
        
    inv_item.amount -= 1
    if inv_item.amount <= 0:
        db.session.delete(inv_item)
    db.session.commit()
    
    stocks = Stock.query.all()
    items = [s.name for s in stocks]
    weights = [max(1.5 - s.value, 0.1) for s in stocks]
    
    rolled = [random.choices(items, weights=weights, k=1)[0] for _ in range(2)]
    won = (rolled[0] == rolled[1])
    
    if won:
        win_trade = TradeRequest(user_id=current_user.id, username=current_user.username, item_name=item_name, amount=2, type="WIN", status="Bekliyor")
        db.session.add(win_trade)
        db.session.commit()
        db.session.add(ChatMessage(trade_id=win_trade.id, sender_username="Sistem", message=f"Tebrikler kazandınız! Ödül: 2x {item_name}"))
        db.session.commit()
    
    return {"status": "success", "rolled": rolled, "won": won}

@app.route('/chat/<int:trade_id>', methods=['GET', 'POST'])
@login_required
def chat(trade_id):
    trade = TradeRequest.query.get_or_404(trade_id)
    if current_user.username != 'RealSaatYilmaz' and trade.user_id != current_user.id:
        flash('Yetkiniz yok!', 'danger')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        msg = request.form.get('message')
        if msg:
            db.session.add(ChatMessage(trade_id=trade.id, sender_username=current_user.username, message=msg))
            db.session.commit()
        return redirect(url_for('chat', trade_id=trade.id))
        
    messages = ChatMessage.query.filter_by(trade_id=trade.id).all()
    return render_template('chat.html', trade=trade, messages=messages)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
