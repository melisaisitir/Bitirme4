from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session management

def init_db():
    with sqlite3.connect('users.db', timeout=10) as conn:  # Set timeout to 10 seconds
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS User (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                password TEXT NOT NULL,
                dob TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                gender TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
            )
        ''')
        conn.commit()

init_db()

@app.route('/')
def home():
    if 'username' in session:
        return render_template('home_logged_in.html', username=session['username'])
    return render_template('Home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        with sqlite3.connect('users.db', timeout=10) as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM User WHERE email = ?', (email,))
            user = c.fetchone()
        
        if user and check_password_hash(user[3], password):  # Assuming password is the 4th column
            session['username'] = user[1]  # Assuming first name is the 2nd column
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first-name']
        last_name = request.form['last-name']
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        dob = request.form['dob']
        phone = request.form['phone']
        gender = request.form['gender']
        email = request.form['email']

        if password != confirm_password:
            flash('Passwords do not match!')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='sha256')
        
        try:
            with sqlite3.connect('users.db', timeout=10) as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO User (first_name, last_name, password, dob, phone, gender, email)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (first_name, last_name, hashed_password, dob, phone, gender, email))
                conn.commit()
            flash('Registration successful! You can now log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/about')
def about():
    if 'username' in session:
        return render_template('about_logged_in.html', username=session['username'])
    return render_template('about.html')

@app.route('/create')
def create():
    if 'username' not in session:
        flash('You need to be logged in to access this page.')
        return redirect(url_for('login'))
    return render_template('create.html', username=session['username'])


@app.route('/books')
def books():
    if 'username' not in session:
        flash('You need to be logged in to access this page.')
        return redirect(url_for('login'))
    return render_template('books.html', username=session['username'])


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
