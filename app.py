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

# Adminin Sitede Tanımladığı Stoklar ve Valueleri
class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Float, nullable=False)

# Kullanıcının Sahip Olduğu Onaylanmış Eşyalar
class UserInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Integer, default=1)

# Talepler (Yatırma veya Kazanılan Ödülü Teslim Etme)
class TradeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(150), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Integer, default=1)
    type = db.Column(db.String(20), default="DEPOSIT")
    status = db.Column(db.String(50), default="Bekliyor")
    messages = db.relationship('ChatMessage', backref='trade', cascade="all, delete-orphan")

# 📌 CANLI SOHBET MESAJLARI TABLOSU
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trade_id = db.Column(db.Integer, db.ForeignKey('trade_request.id'), nullable=False)
    sender_username = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(500), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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
        password = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')
        
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten kullanılıyor.', 'danger')
            return redirect(url_for('register'))
            
        new_user = User(username=username, email=email, password=password)
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
                new_stock = Stock(name=name, value=value)
                db.session.add(new_stock)
                db.session.commit()
                flash(f'{name} stoğa eklendi (Value: {value})', 'success')
                
        elif action == 'delete_stock':
            stock_id = request.form.get('stock_id')
            stock = Stock.query.get(stock_id)
            if stock:
                db.session.delete(stock)
                db.session.commit()
                flash('Stok silindi!', 'info')
                
        elif action in ['approve_trade', 'reject_trade']:
            trade_id = request.form.get('trade_id')
            trade = TradeRequest.query.get(trade_id)
            if trade and trade.status == "Bekliyor":
                if action == 'approve_trade':
                    trade.status = "Onaylandı / Teslim Edildi"
                    if trade.type == "DEPOSIT":
                        inv_item = UserInventory.query.filter_by(user_id=trade.user_id, item_name=trade.item_name).first()
                        if inv_item:
                            inv_item.amount += trade.amount
                        else:
                            new_inv = UserInventory(user_id=trade.user_id, item_name=trade.item_name, amount=trade.amount)
                            db.session.add(new_inv)
                        flash(f'{trade.username} kullanıcısının {trade.amount}x {trade.item_name} yatırımı onaylandı!', 'success')
                    elif trade.type == "WIN":
                        flash(f'{trade.username} kullanıcısına {trade.amount}x {trade.item_name} ödülü verildi olarak işaretlendi!', 'success')
                    db.session.commit()
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

    if amount < 1 or amount > 100:
        flash('Lütfen 1 ile 100 arasında geçerli bir adet giriniz!', 'danger')
        return redirect(url_for('index'))
    
    stock_check = Stock.query.filter_by(name=item_name).first()
    if not stock_check:
        flash('Geçersiz veya stokta olmayan eşya!', 'danger')
        return redirect(url_for('index'))
        
    new_trade = TradeRequest(
        user_id=current_user.id,
        username=current_user.username,
        item_name=item_name,
        amount=amount,
        type="DEPOSIT",
        status="Bekliyor"
    )
    db.session.add(new_trade)
    db.session.commit()
    
    # Otomatik hoş geldin mesajı ekleyelim
    welcome_msg = ChatMessage(trade_id=new_trade.id, sender_username="Sistem", message=f"{current_user.username} yatırma talebi oluşturdu. Admin (RealSaatYilmaz) ile buraya yazarak anlaşabilirsiniz.")
    db.session.add(welcome_msg)
    db.session.commit()

    flash(f'{amount}x {item_name} yatırma talebi gönderildi! Canlı sohbetten adminle konuşabilirsin.', 'info')
    return redirect(url_for('index'))

@app.route('/rng', methods=['POST'])
@login_required
def rng():
    item_name = request.form.get('item_name')
    
    inv_item = UserInventory.query.filter_by(user_id=current_user.id, item_name=item_name).first()
    if not inv_item or inv_item.amount < 1:
        return {"status": "error", "message": "Bu eşyaya sahip değilsiniz veya stokunuz yetersiz!"}
        
    inv_item.amount -= 1
    if inv_item.amount <= 0:
        db.session.delete(inv_item)
    db.session.commit()
    
    stocks = Stock.query.all()
    if not stocks:
        return {"status": "error", "message": "Sitede kayıtlı stok bulunmuyor!"}
        
    items = [s.name for s in stocks]
    weights = [max(1.5 - s.value, 0.1) for s in stocks]
    
    rolled = [random.choices(items, weights=weights, k=1)[0] for _ in range(2)]
    won = (rolled[0] == rolled[1])
    
    if won:
        win_trade = TradeRequest(
            user_id=current_user.id,
            username=current_user.username,
            item_name=item_name, # Koyduğu eşyanın adı
            amount=2,            # 2 katı
            type="WIN",
            status="Bekliyor"
        )
        db.session.add(win_trade)
        db.session.commit()
        
        # Otomatik sohbet mesajı
        welcome_msg = ChatMessage(trade_id=win_trade.id, sender_username="Sistem", message=f"Tebrikler! {item_name} oyununu kazandınız. Ödülü almak için adminle buradan iletişime geçin.")
        db.session.add(welcome_msg)
        db.session.commit()
    
    return {
        "status": "success",
        "rolled": rolled,
        "won": won
    }

# 📌 CANLI SOHBET SAYFASI ROUTE'U
@app.route('/chat/<int:trade_id>', methods=['GET', 'POST'])
@login_required
def chat(trade_id):
    trade = TradeRequest.query.get_or_404(trade_id)
    
    # Sadece ilgili kullanıcı veya admin (RealSaatYilmaz) girebilir
    if current_user.username != 'RealSaatYilmaz' and trade.user_id != current_user.id:
        flash('Bu sohbet odasına erişim yetkiniz yok!', 'danger')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        msg_text = request.form.get('message')
        if msg_text:
            new_msg = ChatMessage(trade_id=trade.id, sender_username=current_user.username, message=msg_text)
            db.session.add(new_msg)
            db.session.commit()
        return redirect(url_for('chat', trade_id=trade.id))
        
    messages = ChatMessage.query.filter_by(trade_id=trade.id).all()
    return render_template('chat.html', trade=trade, messages=messages)

if __name__ == '__main__':
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
    app.run(debug=True, host='0.0.0.0', port=5000)