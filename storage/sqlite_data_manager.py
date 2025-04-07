from flask_sqlalchemy import SQLAlchemy
from storage.data_manager_interface import DataManagerInterface
from sqlalchemy import ForeignKey, text, exc
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
import os

db_path = '/Users/daniilkharaman/python/movieweb_app/database/data.db'
DATABASE_URL = f"sqlite:///{db_path}"

class SQLiteDataManager(DataManagerInterface):
    def __init__(self, db_file_name):
        self.db_file_name = db_file_name
        self.db = SQLAlchemy()


    def check_database_connection(self):

        """Checks if the database file exists and verifies that a connection to the database can be established."""

        if not os.path.exists(db_path):
            print(f"Database file was not found: {db_path}")
            return False
        try:
            self.db.session.execute(text('SELECT 1'))
            print('Connection established')
            return True
        except (exc.OperationalError, Exception) as e:
            print(f"Impossible to connect with the database: {e}")
            return False


    def get_all_users(self):

        """Retrieves all user accounts from the database."""

        return self.db.session.execute(self.db.select(UserAccount)).scalars()


    def get_user_movies(self, user_id):

        """Fetches all movies associated with a given user ID from the database."""

        return self.db.session.execute(self.db.select(Movie).where(Movie.user_id == user_id)).scalars()


    def get_movie_by_id(self, movie_id):

        """Retrieves a movie record from the database by its movie ID."""

        return self.db.session.get(Movie, movie_id)


    def add_user(self, name):

        """Creates and adds a new user account with the given name to the database."""

        user = UserAccount(
            name=name,
        )
        self.db.session.add(user)
        self.db.session.commit()


    def delete_user(self, user_id):

        """Deletes the user account identified by the given user ID from the database."""

        user = self.db.session.get(UserAccount, user_id)
        self.db.session.delete(user)
        self.db.session.commit()


    def update_user(self, user_id, new_name):

        """Updates the name of an existing user account specified by the user ID."""

        user = self.db.session.get(UserAccount, user_id)
        user.name = new_name
        self.db.session.commit()


    def add_movie(self, title, user_id, director, year, rating, poster):

        """Adds a new movie record with the provided details for a specific user to the database."""

        movie = Movie(
            title=title,
            director=director,
            year=year,
            rating=rating,
            poster=poster,
            user_id=user_id
        )
        self.db.session.add(movie)
        self.db.session.commit()


    def delete_movie(self, movie_id):

        """Removes a movie record from the database using the specified movie ID."""

        movie = self.db.session.get(Movie, movie_id)
        self.db.session.delete(movie)
        self.db.session.commit()


    def update_movie(self, movie_id, title, director, year, rating, poster):

        """Updates an existing movie record with new information including title, director, year, rating, and poster."""

        movie = self.db.session.get(Movie, movie_id)
        movie.title = title
        movie.director = director
        movie.year = year
        movie.rating = rating
        movie.poster = poster
        self.db.session.commit()


    def user_in_database(self, user_name):

        """Checks if a user with the specified name exists in the database."""

        if not self.db.session.execute(self.db.select(UserAccount).where(UserAccount.name == user_name)).all():
            return False
        return True


    def movie_in_database(self, movie_title, user_id):

        """Checks if a movie with the specified title exists for the given user ID in the database."""

        if not self.db.session.execute(self.db.select(Movie).where(Movie.title == movie_title, Movie.user_id == user_id)).all():
            return False
        return True


data_manager = SQLiteDataManager(DATABASE_URL)
db = data_manager.db


class UserAccount(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True)
    movies: Mapped[List['Movie']] = relationship(back_populates='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"UserAccount(id={UserAccount.id}, name={UserAccount.name})"


class Movie(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str]
    director: Mapped[Optional[str]]
    year: Mapped[Optional[int]]
    rating: Mapped[Optional[float]]
    poster: Mapped[Optional[str]]
    user_id: Mapped[int] = mapped_column(ForeignKey('user_account.id'))
    user : Mapped['UserAccount'] = relationship(back_populates='movies')

    def __repr__(self):
        return (f"Movie(id={Movie.id}, title={Movie.title}, director={Movie.director},"
                f"year={Movie.year}, rating={Movie.rating})")
