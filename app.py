from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/poll_images'
app.config['ID_UPLOAD_FOLDER'] = 'static/id_uploads'

db = SQLAlchemy(app)

# ===================== Models =====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200))
    email = db.Column(db.String(100))
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    front_id_image = db.Column(db.String(255))
    back_id_image = db.Column(db.String(255))

class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255), nullable=False)
    poll_name = db.Column(db.String(255))
    image_url = db.Column(db.String(255))
    contestant1_name = db.Column(db.String(100))
    contestant1_image = db.Column(db.String(255))
    contestant2_name = db.Column(db.String(100))
    contestant2_image = db.Column(db.String(255))
    choices = db.relationship('Choice', backref='poll', lazy=True)

class Choice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    choice_text = db.Column(db.String(255), nullable=False)
    votes = db.Column(db.Integer, default=0)

class VotedUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'poll_id', name='_user_poll_uc'),)

# ===================== Helpers =====================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Fadlan login samee")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Kaliya admin ayaa geli kara")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def save_file(file, folder=None):
    if file and file.filename:
        filename = secure_filename(file.filename)
        target_folder = folder or app.config['UPLOAD_FOLDER']
        os.makedirs(target_folder, exist_ok=True)
        filepath = os.path.join(target_folder, filename)
        file.save(filepath)
        return filename
    return None

# Waxaan ka saaray extract_name_from_id sababtoo ah OCR ma jirto

# ===================== Routes =====================
@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('index'))
        else:
            flash("Xogta waa khalad")
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = request.form['full_name'].strip()
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash("Username hore ayaa loo isticmaalay")
            return redirect(url_for('signup'))

        front_id = request.files.get('front_id')
        back_id = request.files.get('back_id')

        if not front_id or not back_id:
            flash("Fadlan labada ID sawir ka dhig mid sax ah")
            return redirect(url_for('signup'))

        front_filename = save_file(front_id, app.config['ID_UPLOAD_FOLDER'])
        back_filename = save_file(back_id, app.config['ID_UPLOAD_FOLDER'])

        # **Halkan kama fiirinno OCR oo magaca sawirka laga helayo**
        # Kaliya hubi in magaca user-ka iyo sawirku jiraan

        user = User(
            full_name=full_name,
            email=email,
            username=username,
            password=password,
            front_id_image=front_filename,
            back_id_image=back_filename
        )
        db.session.add(user)
        db.session.commit()
        flash("Signup guuleystay, fadlan login samee")
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/index')
@login_required
def index():
    poll = Poll.query.order_by(Poll.id.desc()).first()
    if not poll:
        return "No poll found. Admins can create one."
    return render_template('index.html', poll=poll)

@app.route('/vote', methods=['POST'])
@login_required
def vote():
    user_id = session['user_id']
    poll = Poll.query.order_by(Poll.id.desc()).first()
    if not poll:
        flash("Poll lama helin.")
        return redirect(url_for('index'))

    existing_vote = VotedUser.query.filter_by(user_id=user_id, poll_id=poll.id).first()
    if existing_vote:
        return render_template('results.html', poll=poll, voted_warning=True)

    choice_id = request.form.get('choice')
    if choice_id:
        choice = Choice.query.get(choice_id)
        if choice and choice.poll_id == poll.id:
            choice.votes += 1
            db.session.add(VotedUser(user_id=user_id, poll_id=poll.id))
            db.session.commit()
            return render_template('results.html', poll=poll, voted=True)

    flash("Fadlan dooro doorasho sax ah.")
    return redirect(url_for('index'))

@app.route('/results')
@login_required
def results():
    poll = Poll.query.order_by(Poll.id.desc()).first()
    return render_template('results.html', poll=poll)

@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    if request.method == 'POST':
        question = request.form['question']
        poll_name = request.form['poll_name']
        poll_image = save_file(request.files.get('poll_image'))

        contestant1_name = request.form['contestant1_name']
        contestant2_name = request.form['contestant2_name']
        contestant1_image = save_file(request.files.get('contestant1_image'))
        contestant2_image = save_file(request.files.get('contestant2_image'))

        poll = Poll(
            question=question,
            poll_name=poll_name,
            image_url=poll_image,
            contestant1_name=contestant1_name,
            contestant1_image=contestant1_image,
            contestant2_name=contestant2_name,
            contestant2_image=contestant2_image
        )
        db.session.add(poll)
        db.session.flush()

        for choice in request.form.getlist('choices'):
            if choice.strip():
                db.session.add(Choice(poll_id=poll.id, choice_text=choice.strip()))

        db.session.commit()
        flash("Poll created successfully")
        return redirect(url_for('admin'))

    poll = Poll.query.order_by(Poll.id.desc()).first()
    return render_template('admin.html', poll=poll)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ===================== DB Init =====================
if __name__ == '__main__':
    with app.app_context():
        if os.path.exists("db.sqlite3"):
            os.remove("db.sqlite3")
        db.create_all()

        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', password='admin123', is_admin=True)
            db.session.add(admin_user)

        if not Poll.query.first():
            default_poll = Poll(
                question='Yaa noqonaya Madaxwaynaha Puntland',
                poll_name='Doorashada Madaxweynaha Dowlada P',
                contestant1_name='Dr. Maxamed',
                contestant2_name='Dr. Ayaanle'
            )
            db.session.add(default_poll)
            db.session.flush()
            db.session.add_all([
                Choice(poll_id=default_poll.id, choice_text='Dr. Maxamed'),
                Choice(poll_id=default_poll.id, choice_text='Dr. Ayaanle')
            ])
        db.session.commit()

    app.run(debug=True)
