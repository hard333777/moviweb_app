from flask import Flask, render_template, request, flash, redirect, url_for
from storage.sqlite_data_manager import data_manager, db, UserAccount, Movie
from datetime import datetime
import os
from dotenv import load_dotenv
import requests
from flask_migrate import Migrate
from sqlalchemy import exc


load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
API_KEY = os.getenv('API_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = data_manager.db_file_name
migrate = Migrate(app, db)
try:
    db.init_app(app)
except exc.ArgumentError as e:
    print(f"Impossible to connect to the database: {e}")
    quit()



def validate_username(username: str):
    if not username or username.isspace():
        flash('Name must not be blank!', 'error')
        return False
    if len(username) > 30:
        flash('Maximum 30 characters are allowed!', 'error')
        return False
    if data_manager.user_in_database(username):
        flash('User is already existed. Choose another name.', 'error')
        return False
    return True


def validate_movie_data(title, director=None, year=None, rating=None, poster=None):
    if not title or title.isspace():
        flash('Title must not be blank!', 'error')
        return False
    if title and len(title) > 30:
        flash('Maximum 30 characters are allowed!', 'error')
        return False
    if director and director.isspace():
        flash('Only spaces are not allowed', 'error')
        return False
    if director and len(director) > 30:
        flash('Maximum 30 characters are allowed!', 'error')
        return False
    if year:
        try:
            year = int(year)
            min_year = 1890
            max_year = datetime.now().year
            if year < min_year or year > max_year:
                flash('Wrong format of the year!', 'error')
                return False
        except (ValueError, Exception) as e:
            print(f"Wrong format of the year: {e}")
            flash('Wrong format of the year!', 'error')
            return False
    if rating:
        try:
            rating = float(rating)
            if rating > 10 or rating < 0:
                flash('Wrong format of the rating! Maximum: 10, Minimum: 0.', 'error')
                return False
        except (ValueError, Exception) as e:
            print(f"Wrong format of the rating: {e}")
            flash('Wrong format of the rating!', 'error')
            return False
    if poster and poster.isspace():
        flash('Only spaces are not allowed', 'error')
        return False
    return title, director, year, rating, poster


def get_data_api(movie_input, user_id):

    """Validates data from the API and returns it"""
    try:
        endpoint = f"http://www.omdbapi.com/?apikey={API_KEY}&t={movie_input}"
        response = requests.get(endpoint)
        parsed_response = response.json()
        if parsed_response == {"Response": "False", "Error": "Movie not found!"}:
            raise ValueError("Such movie doesn't exist!")

        title = parsed_response['Title']
        if not title or title == 'N/A':
            raise ValueError('Impossible to add the movie!')
        if data_manager.movie_in_database(title, user_id):
            raise ValueError('The movie is already in the database.')

        year = parsed_response['Year']
        if not year or year == 'N/A':
            year = None
        if '–' in year:
            year = year.split('–')[0]
            year = ''.join(year)
        if year:
            year = int(year)

        rating = parsed_response['imdbRating']
        if not rating or rating == 'N/A':
            rating = None
        if rating:
            rating = float(rating)

        poster = parsed_response['Poster']
        if not poster or poster == 'N/A':
            poster = None

        director = parsed_response['Director']
        if not director or director == 'N/A':
            director = None

        return title, year, rating, poster, director
    except requests.exceptions.ConnectionError as e:
        print(f"Impossible to connect to the API: {e}")
        flash('Problem with the internet connection.', 'error')
    except requests.exceptions.JSONDecodeError as e:
        print(f"No data from the API: {e}")
        flash('Something went wrong, try again later.', 'error')
    except ValueError as e:
        print(f"The following error has occurred: {e}")
        flash(str(e), 'error')
    except Exception as e:
        print(f'The following error has occurred: {e}')
        flash('Something went wrong, try again later.', 'error')


@app.errorhandler(exc.OperationalError)
def operational_error(e):
    flash('Technical works, try again later!', 'error')
    print(f"Impossible to connect to the database: {e}")
    return render_template('error.html'), 500


@app.get('/')
def home():
    return render_template('home.html')


@app.get('/users')
def list_all_users():
    users = data_manager.get_all_users()
    return render_template('users.html', users=users)


@app.get('/users/<user_id>/')
def user_movies(user_id):
    movies = data_manager.get_user_movies(user_id)
    return render_template('user_movies.html', movies=movies)


@app.post('/users/<user_id>')
def delete_user_from_db(user_id):
    data_manager.delete_user(user_id)
    flash('User is successfully deleted.', 'info')
    return redirect(url_for('list_all_users'))


@app.route('/add_user', methods=['GET', 'POST'])
def add_user_to_db():
    if request.method == 'POST':
        user_name = request.form.get('name')
        if validate_username(user_name):
            data_manager.add_user(user_name)
            flash('User is successfully added', 'info')
    return render_template('add_user.html')


@app.route('/users/<user_id>/add_movie', methods=['GET', 'POST'])
def add_movie_to_db(user_id):
    if request.method == 'POST':
        title = request.form.get('title')
        if validate_movie_data(title):
            movie_to_add = get_data_api(title, user_id)
            if movie_to_add:
                title, year, rating, poster, director = movie_to_add
                data_manager.add_movie(title=title, year=year, rating=rating,
                                       poster=poster, director=director, user_id=user_id)
                flash('Movie is successfully added.', 'info')
    return render_template('add_movie.html')


@app.route('/users/<user_id>/update_movie/<movie_id>', methods=['GET', 'POST'])
def update_movie_in_db(user_id, movie_id):
    if request.method == 'POST':
        title = request.form.get('title')
        director = request.form.get('director')
        year = request.form.get('year')
        rating = request.form.get('rating')
        poster = request.form.get('poster')
        movie_to_update = validate_movie_data(title, director, year, rating, poster)
        if movie_to_update:
            title, director, year, rating, poster = movie_to_update
            data_manager.update_movie(movie_id=movie_id, title=title, director=director,
                                      year=year, rating=rating, poster=poster)
            flash('Movie is successfully updated.', 'info')
    movie = data_manager.get_movie_by_id(movie_id)
    return render_template('update_movie.html', movie=movie)


@app.post('/users/<user_id>/delete_movie/<movie_id>')
def delete_movie_from_db(user_id, movie_id):
    data_manager.delete_movie(movie_id)
    flash('Movie is successfully deleted.', 'info')
    return redirect(url_for('user_movies', user_id=user_id))





if __name__ == '__main__':
    with app.app_context():
        if data_manager.check_database_connection():
            app.run(debug=True)
        else:
            exit(1)

