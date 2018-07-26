from flask import Flask, render_template, jsonify, redirect, request, url_for
from flask import session as login_session
import random
import string
from datetime import date
from oauth2client.client import flow_from_clientsecrets, AccessTokenCredentials
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker, joinedload
from database_setup import Base, Items, Categories, Users


app = Flask(__name__)


# Constants required for the app to work.
engine = create_engine('sqlite:///catalogApp_2.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()
CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
app.secret_key = json.loads(open('client_secrets.json', 'r').read())[
    'web']['client_secret']


# Code to create a new user in the Users table.
# Code was adapted from Udacity local permission system.
def createUser(login_session):
    session = DBSession()
    current_highest = session.query(Users).order_by(
        Users.user_id.desc()).first()
    new_user_id = current_highest.user_id + 1
    new_user = Users(
        user_name=login_session['username'],
        user_email=login_session['email'],
        user_id=new_user_id)
    session.add(new_user)
    session.commit()
    user = session.query(Users).filter_by(
        user_email=login_session['email']).one()
    return user.user_id


# Code to get user info from a user id.
# Code adapted from Udacity local permission system.
def getUserInfo(user_id):
    session = DBSession()
    user = session.query(Users).filter_by(user_id=user_id).one()
    return user

# Code to get user id based on email.
# Code was adapted from Udacity local permission system.


def getUserId(email):
    session = DBSession()
    try:
        user = session.query(Users).filter_by(user_email=email).one()
        return user.user_id
    except BaseException:
        return False


# Login page function, this was adapted from Udacity's restaraunt code.
@app.route('/login')
def login():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


# Function that connects to Google OAuth services.
# This code was adapted from the Udacity Restaraunt code.
@app.route('/gconnect', methods=['POST'])
def gconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter'),
                                 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    code = request.data
    try:
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps(
            'Failed to upgrade the authorization code.'), 401)
        response.header['Content-Type'] = 'application/json'
        return response
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    if result.get('error') is not None:
        reponse = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_reponse(
            json.dumps("Token's user Id doesn't match given user Id"), 401)
        reponse.headers['Content-Type'] = 'application/json'
        return response
    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
    login_session['credentials'] = access_token
    login_session['gplus_id'] = gplus_id
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    data = answer.json()
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    previous_user = getUserId(login_session['email'])
    if not previous_user:
        createUser(login_session)
    return render_template('login.html')


# Creates the JSON endpoint for the items table.
@app.route('/items/json')
def itemsJson():
    session = DBSession()
    item_collection = session.query(Items).all()
    serializable_list = []
    for item in item_collection:
        var_collection = vars(item)
        del var_collection['_sa_instance_state']
        serializable_list.append(var_collection)
    return jsonify(serializable_list)


# Lets the user access the endpoints for specific items.
@app.route('/items/<item_name>/json')
def specifiItemJson(item_name):
    session = DBSession()
    try:
        specific_item = session.query(Items).filter(
            Items.title.like(item_name)).one()
        var_collection = vars(specific_item)
        del var_collection['_sa_instance_state']
        return jsonify(var_collection)
    except BaseException:
        return redirect(url_for('notFound'))


# Lets the user access the endpoints for specific items.
@app.route('/categories/<category_name>/json')
def specificCategoryJson(category_name):
    session = DBSession()
    serializable_list = []
    try:
        category_items = session.query(Items).join(Categories).filter(
            Categories.categoryName.like(category_name)).all()
    except BaseException:
        return redirect(url_for('notFound'))
    for info in category_items:
        var_collection = vars(info)
        del var_collection['_sa_instance_state']
        serializable_list.append(var_collection)
    return jsonify(serializable_list)


# Creates the endpoint for the categories table.
@app.route('/categories/json')
def categoriesJson():
    session = DBSession()
    item_collection = session.query(Categories).all()
    serializable_list = []
    for item in item_collection:
        var_collection = vars(item)
        del var_collection['_sa_instance_state']
        serializable_list.append(var_collection)
    return jsonify(serializable_list)


# Function that provides the sign out functionality for the app
# This function was adapted from the Udacity restaraunt code.
@app.route('/gdisconnect')
def gdisconnect():
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(json.dumps('Current user not connected'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = login_session['credentials']
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    print(url)
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print(result)
    if result['status'] == '200':
        del login_session['credentials']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        response = make_response(json.dumps('Successfully disconnected.'))
        response.headers['Content-Type'] = 'application/json'
        return redirect(url_for('landingPage'))
    else:
        response = make_response(
            json.dumps('Failed to revoke token for user'), 400)
        response.headers["Content-Type"] = 'application/json'
        return redirect(url_for('notFound'))


# Provides the first point of contact for the editing functionality.
# Also redirects to a 404 if the user isn't signed in or tries to
# Manuallyt enter an item to edit that doesn't exist.
@app.route('/<item_name>/edit')
def editItem(item_name):
    session = DBSession()
    data = session.query(Categories).all()
    access_token = login_session.get('credentials')
    all_items = session.query(Items).all()
    this_item = session.query(Items).filter(
        Items.title.like(item_name)).first()
    if access_token is None:
        return render_template('404.html')
    item_list = []
    for item in all_items:
        item_list.append(item.title)
    if item_name not in item_list:
        return render_template('404.html')
    this_item = session.query(Items).filter(
        Items.title.like(item_name)).first()
    if this_item.user_id != getUserId(login_session.get('email')):
        return render_template('404.html')
    item_name = item_name.replace(" ", "%")
    return render_template('edit.html', data=data, item_name=item_name)


# Performs the final database alterations entered by the user.
# Redirects the user back to the landing page.
@app.route('/edit_final', methods=['POST'])
def edit_final():
    form = request.form
    original_item = form['item_being_edited'].replace("%", " ")
    item_category_title = form['category']
    new_item_name = form['item_name']
    new_desc = form['item_desc']
    session = DBSession()
    new_category_id = session.query(Categories).filter(
        Categories.categoryName.like(item_category_title)).all()
    item_to_change = session.query(Items).filter(
        Items.title.like(original_item)).first()
    item_to_change.title = new_item_name
    item_to_change.categoryIds = new_category_id[0].id
    item_to_change.description = new_desc
    session.add(item_to_change)
    session.commit()
    return redirect(url_for('landingPage'))


# First point of contact for the add item.
# Redirects the user ot a 404 if ths user
# Is not signed in.
@app.route('/<cat_name>/additem')
def addItem(cat_name):
    session = DBSession()
    access_token = login_session.get('credentials')
    user_id = getUserId(login_session.get('email'))
    data = session.query(Categories).all()
    if access_token is None:
        return render_template('404.html')
    categoryNames = []
    for category in data:
        categoryNames.append(category.categoryName)
    if cat_name not in categoryNames:
        return redirect('/404', code=404)
    return render_template('add.html', cat_name=cat_name, user_id=user_id)


# Performs the actual database alterations to add an item.
@app.route('/add_final', methods=['POST'])
def add_final():
    form = request.form
    dateAdded = str(date.today()).replace("-", "")
    item_category_title = form['category_name']
    new_item_name = form['item_name']
    new_desc = form['item_desc']
    user_id = form['user_id']
    session = DBSession()
    category_id = session.query(Categories).filter(
        Categories.categoryName.like(item_category_title)).first()
    new_item = Items(
        title=new_item_name,
        categoryIds=category_id.id,
        dateAdded=dateAdded,
        user_id=user_id,
        description=new_desc)
    try:
        session.add(new_item)
        session.commit()
    except BaseException:
        return render_template('404.html')
    return redirect(url_for('landingPage'))


# Opens the form for the user to try to delete an item.
# Redirects to a 404 if the user is not signed in.
@app.route('/<item_name>/delete')
def deleteConfirmation(item_name):
    session = DBSession()
    try:
        to_be_deleted = session.query(Items).filter(
            Items.title.like(item_name)).one()
    except BaseException:
        return render_template('404.html')
    current_user_id = getUserId(login_session.get('email'))
    origin_user_id = to_be_deleted.user_id
    if current_user_id != origin_user_id:
        return render_template('404.html')
    return render_template('delete.html', item_name=item_name)


# Final deletion path that actually deletes the info
# From the database.
@app.route('/<item_name>/item_deleted', methods=['POST'])
def deleteItem(item_name):
    form = request.form
    session = DBSession()
    try:
        query = session.query(Items).filter(Items.title.like(item_name))
        query.delete(synchronize_session=False)
        session.commit()
        session.expire_all()
        return redirect(url_for('landingPage'))
    except BaseException:
        print('Item not found')
        return render_template('404.html')


# Page that displays the specific item a user clicks.
@app.route('/<item_name>')
def itemPage(item_name):
    session = DBSession()
    data = session.query(Categories).all()
    item_in_question = session.query(Items).filter(
        Items.title.like(item_name)).first()
    try:
        origin_user_id = item_in_question.user_id
    except BaseException:
        origin_user_id = None
    current_user_id = getUserId(login_session.get('email'))
    if not current_user_id:
        current_user_id = 'Unauthorized'
    editable_by_current_user = False
    if origin_user_id == current_user_id:
        editable_by_current_user = True
    return render_template(
        'item.html',
        item=item_in_question,
        data=data,
        editable_by_current_user=editable_by_current_user)


# Displays all the items in a particular category.
@app.route('/<cat_name>/items')
def catPage(cat_name):
    session = DBSession()
    data = session.query(Categories).all()
    categoryNames = []
    for category in data:
        categoryNames.append(category.categoryName)
    if cat_name not in categoryNames:
        return redirect('/404', code=404)
    cat_items = session.query(Items).join(Categories).filter(
        Categories.categoryName.like('%' + cat_name + '%')).all()
    return render_template(
        'category.html',
        data=data,
        cat_items=cat_items,
        cat_name=cat_name)


# Renders the error 404 page.
@app.route('/404')
def notFound():
    return render_template('404.html')


# Show's the landing page, allows the user to see the 9 most recent items.
@app.route('/index')
@app.route('/')
def landingPage():
    session = DBSession()
    data = session.query(Categories).all()
    latestItems = session.query(Items).order_by(
        Items.dateAdded.desc()).limit(9).all()
    return render_template(
        'index.html',
        login_session=login_session,
        data=data,
        latestItems=latestItems)


# Main method that starts the server.
if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
