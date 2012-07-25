from comics8 import ComicsAccount
from flask import Flask, session, redirect, url_for, escape, request, render_template

app = Flask(__name__)

@app.route('/')
def index():
    if not 'username' in session or not 'password' in session:
        return redirect(url_for('login'))

    account = ComicsAccount(session['username'])
    account.login(session['password'])
    collection = account.get_collection()
    return render_template(
            'index.html', 
            title="Your Collection",
            username=session['username'],
            collection=collection
            )


@app.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form['username']
        session['password'] = request.form['password']
        return redirect(url_for('index'))
    return render_template(
            'login.html',
            title="Login to Comixology"
            )


app.secret_key = '$*^%&#53r3ret56$%@#Res'

if __name__ == "__main__":
    app.debug = True
    app.run()

