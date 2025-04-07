from flask import Flask, render_template, request, flash, redirect, url_for
from storage.sqlite_data_manager import data_manager, db
from datetime import datetime
import os
from dotenv import load_dotenv
import requests
from flask_migrate import Migrate
from sqlalchemy import exc
from genai.movies_rec_ai import get_instructions, open_chat, get_chat_ai_recommendations
import functools


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

users_chats = dict()


def validate_username(username: str):

    """Validates the username by ensuring it is non-empty, within 30 characters, and not already in the database."""

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

    """Validates the movie data by checking that the title is non-empty and within limits, and that optional fields (director, year, rating, poster) are properly formatted."""

    if not title or title.isspace():
        flash('Title must not be blank!', 'error')
        return False
    if title and len(title) > 100:
        flash('Maximum 100 characters are allowed!', 'error')
        return False
    if director and director.isspace():
        flash('Only spaces are not allowed', 'error')
        return False
    if director and len(director) > 100:
        flash('Maximum 100 characters are allowed!', 'error')
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


def validate_data_api(func):

    """Decorator that wraps an API function to handle exceptions and flash error messages for API-related errors."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            data = func(*args, **kwargs)
            return data
        except requests.exceptions.ConnectionError as e:
            print(f"Impossible to connect to the API: {e}")
            flash('Problem with the internet connection.', 'error')
        except requests.exceptions.JSONDecodeError as e:
            print(f"No data from the API: {e}")
            flash('Something went wrong, try again later.', 'error')
        except ValueError as e:
            print(f"The following error has occurred: {e}")
            e = str(e)
            if not 'hidden' in e:
                flash(e, 'error')
        except Exception as e:
            print(f'The following error has occurred: {e}')
            flash('Something went wrong, try again later.', 'error')
    return wrapper


@validate_data_api
def get_data_api(movie_input, user_id):

    """Fetches and processes movie data from the OMDb API for a given movie input and user ID,
    ensuring the movie exists and is not already added."""

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


@validate_data_api
def get_data_api_chat(movie_input):

    """Fetches the movie poster from the OMDb API for a given movie input, intended for chat-based recommendations."""

    endpoint = f"http://www.omdbapi.com/?apikey={API_KEY}&t={movie_input}"
    response = requests.get(endpoint)
    parsed_response = response.json()
    if parsed_response == {"Response": "False", "Error": "Movie not found!"}:
        raise ValueError("Such movie doesn't exist!/hidden")

    poster = parsed_response['Poster']
    if not poster or poster == 'N/A':
        poster = None

    return poster


def get_rec_movies_with_poster(rec_movies):

    """Enhances a list of recommended movies by fetching and appending poster data to each movie entry."""

    rec_movies_with_poster = []
    for movie in rec_movies:
        poster = get_data_api_chat(movie.get('title'))
        if poster:
            movie.update({'poster': poster})
            rec_movies_with_poster.append(movie)
    return rec_movies_with_poster


def processing_add_movie(user_id):

    """Processes a POST request to add a movie for a user by validating input data and adding the movie using API data."""

    if request.method == 'POST':
        title = request.form.get('title')
        if validate_movie_data(title):
            movie_to_add = get_data_api(title, user_id)
            if movie_to_add:
                title, year, rating, poster, director = movie_to_add
                data_manager.add_movie(title=title, year=year, rating=rating,
                                       poster=poster, director=director, user_id=user_id)
                flash('Movie is successfully added.', 'info')


def process_recommendations_chat(user_id, chat):

    """Processes chat-based movie recommendations by using the user's movies and mood input to generate and enhance recommendations with poster data."""

    movies = data_manager.get_user_movies(user_id)
    movies = [movie.title for movie in movies]
    mood = request.form.get('mood')
    contents = str([movies, mood])
    recommendations = get_chat_ai_recommendations(chat, contents)
    if recommendations:
        recommendations = get_rec_movies_with_poster(recommendations)
    if not recommendations:
        recommendations = []
        flash('Sorry, nothing was found. Try again!', 'error')
    context = {'user_id': user_id, 'recommendations': recommendations}
    return context


@app.errorhandler(exc.OperationalError)
def operational_error(e):

    """Handles operational database errors by flashing an error message and rendering an error page."""

    flash('Technical works, try again later!', 'error')
    print(f"Impossible to connect to the database: {e}")
    return render_template('error.html'), 500


@app.get('/')
def home():

    """Renders the home page."""

    return render_template('home.html')


@app.get('/users')
def list_all_users():

    """Retrieves all users from the database and renders the users list page."""

    users = data_manager.get_all_users()
    return render_template('users.html', users=users)


@app.get('/users/<user_id>/')
def user_movies(user_id):

    """Displays the movies associated with a specific user by rendering the user's movies page."""

    movies = data_manager.get_user_movies(user_id)
    return render_template('user_movies.html', movies=movies)


@app.post('/users/<user_id>')
def delete_user_from_db(user_id):

    """Deletes a specified user from the database and redirects to the list of users with a success message."""

    data_manager.delete_user(user_id)
    flash('User is successfully deleted.', 'info')
    return redirect(url_for('list_all_users'))


@app.route('/add_user', methods=['GET', 'POST'])
def add_user_to_db():

    """Handles requests to add a new user by validating the username and adding the user to the database."""

    if request.method == 'POST':
        user_name = request.form.get('name')
        if validate_username(user_name):
            data_manager.add_user(user_name)
            flash('User is successfully added', 'info')
    return render_template('add_user.html')


@app.route('/users/<user_id>/add_movie', methods=['GET', 'POST'])
def add_movie_to_db(user_id):

    """Processes the addition of a new movie for a given user by validating input
    and fetching movie data, then renders the add movie page."""

    processing_add_movie(user_id)
    return render_template('add_movie.html', user_id=user_id)


@app.route('/users/<user_id>/add_movie_rec', methods=['GET', 'POST'])
def add_rec_movie_to_db(user_id):

    """Processes the addition of a recommended movie for a given user by validating input and fetching movie data,
    then redirects to the user's movies page."""

    processing_add_movie(user_id)
    return redirect(url_for('user_movies', user_id=user_id))


@app.route('/users/<user_id>/update_movie/<movie_id>', methods=['GET', 'POST'])
def update_movie_in_db(user_id, movie_id):

    """Handles movie update requests by validating new movie data, updating the database record,
    and rendering the update movie page."""

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
    context = {'movie': movie, 'user_id': user_id}
    return render_template('update_movie.html', **context)


@app.post('/users/<user_id>/delete_movie/<movie_id>')
def delete_movie_from_db(user_id, movie_id):

    """Deletes a specified movie from the database and redirects to the user's movie list with a success message."""

    data_manager.delete_movie(movie_id)
    flash('Movie is successfully deleted.', 'info')
    return redirect(url_for('user_movies', user_id=user_id))


@app.route('/users/<user_id>/get_recommendations', methods=['GET', 'POST'])
def ai_recommendations(user_id):

    """Handles AI movie recommendation requests by generating recommendations
    based on user movie data and chat input, then rendering the recommendations page."""

    if request.method == 'GET':
        instructions = get_instructions('genai/instructions.txt')
        if not instructions:
            flash('Something went wrong. Try again later!', 'error')
            return redirect(url_for('user_movies', user_id=user_id))
        chat = open_chat(instructions)
        users_chats.update({user_id:chat})
        return render_template('recommendations.html', user_id=user_id)
    if request.method == 'POST':
        movies = data_manager.get_user_movies(user_id)
        movies = [movie.title for movie in movies]
        mood = request.form.get('mood')
        contents = str([movies, mood])
        chat = users_chats.get(user_id)
        chat.get_history()
        recommendations = get_chat_ai_recommendations(chat, contents)
        if recommendations:
            recommendations = get_rec_movies_with_poster(recommendations)
        if not recommendations:
            recommendations = []
            flash('Sorry, nothing was found. Try again!', 'error')
        context = {'user_id': user_id, 'recommendations': recommendations, 'mood': mood}
        return render_template('recommended_movies.html', **context)


if __name__ == '__main__':
    with app.app_context():
        if data_manager.check_database_connection():
            app.run(debug=True)
        else:
            exit(1)
