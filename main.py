from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap
from functools import wraps
from flask import abort
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("DATABASE_URL")
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONFIGURE TABLES


class User(UserMixin, db.Model):
    __tablename__ = 'parent'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)
    children = relationship("BlogPost", back_populates="parent")
    comments = relationship("Comment", back_populates="comment_author")



class BlogPost(UserMixin, db.Model):
    __tablename__ = 'child'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('parent.id'))
    parent = relationship("User", back_populates="children")
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('parent.id'))
    comment_author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey('child.id'))
    parent_post = relationship("BlogPost", back_populates="comments")
db.create_all()
db.session.commit()



login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated, current_user=current_user)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user_name = request.form.get('name')
        user_mail = request.form.get('email')
        user_word = request.form.get('password')
        hashed_password = generate_password_hash(user_word, method='pbkdf2:sha256', salt_length=8)
        blog_user = User(
            name=user_name,
            email=user_mail,
            password=hashed_password,
        )
        all_users = User.query.all()
        if blog_user in all_users:
            flash("This user already exists, please login instead")
            return redirect(url_for('login'))
        else:
            db.session.add(blog_user)
            db.session.commit()
            login_user(blog_user)
            return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form, logged_in=current_user.is_authenticated)


#Create admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        login_email = request.form.get('email')
        login_password = request.form.get('password')
        user = User.query.filter_by(email=login_email).first()
        all_users = User.query.all()
        print(user)
        if user in all_users:
            if check_password_hash(user.password, login_password):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("incorrect password", "error")
                return redirect(url_for("login"))
        else:
            flash("this user does not exist", "error")
            return redirect(url_for("login"))
    # form = CreatePostForm()
    # if request.method == "POST":
    #     pass
    return render_template("login.html", form=form, logged_in=current_user.is_authenticated, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=form.body.data,
            comment_author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()

    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    print(current_user.name)
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            parent=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        print(new_post)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts", current_user=current_user))
    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
