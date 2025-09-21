import os
import secrets
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from paytmchecksum import PaytmChecksum
from flask_babel import Babel
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# SQLAlchemy configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///old_sell_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key_for_dev')

# File Upload Configuration
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
babel = Babel(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_checksum(params, key):
    checksum = PaytmChecksum.generate_checksum(params, key)
    return checksum

def verify_checksum(params, checksum, key):
    return PaytmChecksum.verify_checksum(params, key, checksum)

@babel.localeselector
def get_locale():
    # user browser language
    return request.accept_languages.best_match(['en', 'hi'])

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    upi_id = db.Column(db.String(255), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    image_filename = db.Column(db.String(150), nullable=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller = db.relationship('User', backref='items')
    location = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    is_sold = db.Column(db.Boolean, default=False)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    from_user = db.relationship('User', foreign_keys=[from_user_id])
    to_user = db.relationship('User', foreign_keys=[to_user_id])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_locale_from_request():
    return request.accept_languages.best_match(['en', 'hi'])

# Routes
@app.route('/')
def home():
    items = Item.query.filter_by(is_sold=False).all()
    return render_template('home.html', items=items)

# app.py file
# ...

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        # Yahan 'username' ki jagah 'login_input' use karenge
        login_input = request.form['login_input']
        password = request.form['password']
        
        user = User.query.filter((User.username == login_input) | (User.email == login_input) | (User.phone == login_input)).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        
        existing_user = User.query.filter((User.username == username) | (User.email == email) | (User.phone == phone)).first()
        if existing_user:
            flash('Username, email, or phone number already exists.')
            return redirect(url_for('register'))
            
        new_user = User(username=username, email=email, phone=phone)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/sell', methods=['GET', 'POST'])
@login_required
def sell_item():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = float(request.form['price'])
        currency = request.form.get('currency', 'INR')
        location = request.form['location']
        
        # Ye line ab sahi hai, dost!
        file = request.files.get('image')
        
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
        new_item = Item(
            title=title,
            description=description,
            price=price,
            currency=currency,
            image_filename=filename,
            seller_id=current_user.id,
            location=location
        )
        db.session.add(new_item)
        db.session.commit()
        
        flash('Item listed successfully!')
        return redirect(url_for('home'))
        
    return render_template('sell.html')

@app.route('/item/<int:item_id>')
def item_details(item_id):
    item = Item.query.get_or_404(item_id)
    seller = item.seller
    return render_template('item.html', item=item, seller=seller)

@app.route('/my_items')
@login_required
def my_items():
    items = Item.query.filter_by(seller_id=current_user.id).all()
    return render_template('my_items.html', items=items)

@app.route('/buy/<int:item_id>')
@login_required
def buy_item(item_id):
    item = Item.query.get_or_404(item_id)
    return render_template('buy.html', item=item)

@app.route('/chat/<int:item_id>')
@login_required
def chat_with_seller(item_id):
    item = Item.query.get_or_404(item_id)
    seller_id = item.seller_id
    
    # Get messages between current user and seller
    messages = ChatMessage.query.filter(
        ((ChatMessage.from_user_id == current_user.id) & (ChatMessage.to_user_id == seller_id)) |
        ((ChatMessage.from_user_id == seller_id) & (ChatMessage.to_user_id == current_user.id))
    ).order_by(ChatMessage.timestamp).all()

    return render_template('chat.html', item=item, seller_id=seller_id, messages=messages)

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    data = request.json
    to_user_id = data.get('to_user_id')
    message = data.get('message')
    
    if to_user_id and message:
        new_message = ChatMessage(
            from_user_id=current_user.id,
            to_user_id=to_user_id,
            message=message
        )
        db.session.add(new_message)
        db.session.commit()
        return jsonify({'status': 'success'}), 200
    
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

@app.route('/get_messages/<int:to_user_id>')
@login_required
def get_messages(to_user_id):
    messages = ChatMessage.query.filter(
        ((ChatMessage.from_user_id == current_user.id) & (ChatMessage.to_user_id == to_user_id)) |
        ((ChatMessage.from_user_id == to_user_id) & (ChatMessage.to_user_id == current_user.id))
    ).order_by(ChatMessage.timestamp).all()
    
    message_list = [
        {
            'from_user': msg.from_user.username,
            'message': msg.message,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
        for msg in messages
    ]
    return jsonify(message_list)

@app.route('/get_api_info')
def get_api_info():
    paytm_api_key = os.environ.get('PAYTM_API_KEY', 'not-found')
    paytm_mid = os.environ.get('PAYTM_MID', 'not-found')
    return jsonify({'paytm_mid': paytm_mid, 'paytm_api_key': paytm_api_key})

@app.route('/get_payment_checksum/<string:order_id>/<string:txn_amount>', methods=['GET'])
def get_payment_checksum(order_id, txn_amount):
    paytm_mid = os.environ.get('PAYTM_MID')
    paytm_api_key = os.environ.get('PAYTM_API_KEY')
    
    paytm_params = {
        'MID': paytm_mid,
        'ORDERID': order_id,
        'TXN_AMOUNT': txn_amount
    }
    
    checksum = generate_checksum(paytm_params, paytm_api_key)
    return jsonify({'checksum': checksum})

@app.route('/paytm_redirect', methods=['POST'])
def paytm_redirect():
    if request.form.get('STATUS') == 'TXN_SUCCESS':
        order_id = request.form.get('ORDERID')
        item_id = int(order_id.split('_')[-1])
        item = Item.query.get_or_404(item_id)
        item.is_sold = True
        db.session.commit()
        flash('Payment successful! The item is now marked as sold.')
        return redirect(url_for('home'))
    else:
        flash('Payment failed or cancelled.')
        return redirect(url_for('home'))

# Ye function database tables banata hai aur admin user add karta hai
# @app.before_first_request ko hata diya gaya hai kyunki ye Flask ke naye versions mein kaam nahi karta.
def create_tables():
    db.create_all()
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@example.com', phone='0000000000', is_admin=True, upi_id='your-upi-id@bank')
        admin.set_password('adminpass')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    # Hum create_tables() ko app context ke andar run kar rahe hain
    # Taki database ka setup app chalne se pehle ho jaye.
    with app.app_context():
        create_tables()

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
