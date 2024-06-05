from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import openai
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Initialize the database
def init_db():
    with sqlite3.connect('users.db', timeout=10) as conn:
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
        c.execute('''
            CREATE TABLE IF NOT EXISTS Book (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                story TEXT NOT NULL,
                images TEXT NOT NULL,
                cover_image TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES User(id)
            )
        ''')
        conn.commit()

init_db()

# Function to moderate content
def moderate_content(text):
    openai.api_key = 'open_ai_key'
    response = openai.Moderation.create(
        input=text
    )
    return response['results'][0]['flagged']

# Function to generate story
def generate_story(template, morality, user_text):
    openai.api_key = 'open_ai_key'
    messages = [
        {"role": "system", "content": "You are a creative assistant for generating children's stories."},
        {"role": "user", "content": f"Create a children's story based on the template '{template}' and the moral lesson '{morality}'. Additional details: {user_text}"}
    ]
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=600  # Ensure story is within the 300-600 word range
        )
        story = response['choices'][0]['message']['content'].strip()
        paragraphs = story.split('\n\n')
        
        if len(paragraphs) > 10:
            paragraphs = paragraphs[:10]
        
        return paragraphs
    except openai.error.InvalidRequestError:
        flash("Content flagged by the safety system. Please review your input.")
        return []

# Function to generate images
def generate_images(paragraphs, title):
    openai.api_key = 'open_ai_key'
    images = []
    
    try:
        # Generate cover image based on the title
        response = openai.Image.create(
            prompt=f"Cover image for a children's book titled '{title}'",
            n=1,
            size="256x256"
        )
        cover_image_url = response['data'][0]['url']
        
        # Generate one image for every two paragraphs, up to a maximum of 5 images
        for i in range(0, len(paragraphs), 2):
            if len(images) >= 5:
                break
            prompt_text = ' '.join(paragraphs[i:i+2])
            response = openai.Image.create(
                prompt=prompt_text,
                n=1,
                size="512x512"
            )
            image_url = response['data'][0]['url']
            images.append(image_url)
        
        return cover_image_url, images
    except openai.error.InvalidRequestError:
        flash("Content flagged by the safety system. Please review your input.")
        return "", []

@app.route('/')
def home():
    if 'username' in session:
        return render_template('home_logged_in.html', username=session['username'])
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        with sqlite3.connect('users.db', timeout=10) as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM User WHERE email = ?', (email,))
            user = c.fetchone()
        
        if user and check_password_hash(user[3], password):
            session['username'] = user[1]
            session['user_id'] = user[0]
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

        # Validate date of birth
        dob_date = datetime.strptime(dob, '%Y-%m-%d')
        today = datetime.today()
        age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
        if age < 15:
            flash('You must be at least 15 years old to register.')
            return redirect(url_for('register'))

        # Validate phone number format
        import re
        phone_pattern = re.compile(r'\(\d{3}\) \d{3} \d{2} \d{2}')
        if not phone_pattern.fullmatch(phone):
            flash('Invalid phone number format. Please use the format (532) 297 23 24.')
            return redirect(url_for('register'))

        # Check if phone number is unique
        with sqlite3.connect('users.db', timeout=10) as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM User WHERE phone = ?', (phone,))
            existing_user = c.fetchone()
            if existing_user:
                flash('Phone number already registered. Please use a different phone number.')
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
            flash('Email or phone number already exists')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/about')
def about():
    if 'username' in session:
        return render_template('about_logged_in.html', username=session['username'])
    return render_template('about.html')

@app.route('/create', methods=['GET', 'POST'])
def create():
    if 'username' not in session:
        flash('You need to be logged in to access this page.')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        template = request.form.get('template')
        morality = request.form.get('morality')
        user_text = request.form.get('story_content')

        if moderate_content(user_text):
            flash("Can't generate story because of inappropriate content.")
            return redirect(url_for('create'))

        paragraphs = generate_story(template, morality, user_text)
        
        title = f"{template} Story"
        cover_image_url, images = generate_images(paragraphs, title)
        
        story = '\n\n'.join(paragraphs)
        images_str = ','.join(images)
        
        user_id = session['user_id']
        with sqlite3.connect('users.db', timeout=10) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO Book (user_id, title, story, images, cover_image)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, title, story, images_str, cover_image_url))
            conn.commit()
        
        flash('Book created successfully!')
        return redirect(url_for('books'))
    
    return render_template('create.html', username=session['username'])

@app.route('/books', methods=['GET', 'POST'])
def books():
    if 'username' not in session:
        flash('You need to be logged in to access this page.')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    with sqlite3.connect('users.db', timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT id, title, cover_image FROM Book WHERE user_id = ?', (user_id,))
        books = c.fetchall()

    if request.method == 'POST':
        book_id = request.form.get('book_id')
        with sqlite3.connect('users.db', timeout=10) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM Book WHERE id = ? AND user_id = ?', (book_id, user_id))
            conn.commit()
        flash('Book deleted successfully!')
        return redirect(url_for('books'))
    
    return render_template('books.html', username=session['username'], books=books)

@app.route('/read_book/<int:book_id>')
def read_book(book_id):
    if 'username' not in session:
        flash('You need to be logged in to access this page.')
        return redirect(url_for('login'))
    
    with sqlite3.connect('users.db', timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT title, story, images FROM Book WHERE id = ?', (book_id,))
        book = c.fetchone()
    
    if book:
        title, story, images = book
        images = images.split(',')
        paragraphs = story.split('\n\n')
        pages = zip(paragraphs, images)
        return render_template('read_book.html', book_title=title, book_pages=pages, username=session['username'])
    else:
        flash('Book not found.')
        return redirect(url_for('books'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
