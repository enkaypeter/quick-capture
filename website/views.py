from flask import Blueprint, render_template, flash, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
import pandas
import json
from .models import Note, User, Case
from . import db, UPLOAD_FOLDER
from werkzeug.utils import secure_filename
import os

views = Blueprint('views', __name__)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'py'}
CURR_DIR = current_directory = os.path.dirname(os.path.abspath(__file__))
CASE_PATH = os.path.join(CURR_DIR, UPLOAD_FOLDER)
print(CURR_DIR)
print(CASE_PATH)

@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        note = request.form.get('note')

        if len(note) < 1:
            flash('Note is too short!', category='error')
        else:
            new_note = Note(data=note, user_id=current_user.id)
            db.session.add(new_note)
            db.session.commit()
            flash('Note added!', category='success')

    return render_template("home.html", user=current_user)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@views.route('/test', methods=['GET', 'POST'])
def test():
    if request.method == 'POST':
        caseName = request.form.get('formCaseName')
        caseDetail = request.form.get('formCaseDetail')
        
        # check if the post request has the file part
        if 'file' not in request.files:
            new_case = Case(caseName=caseName, caseDetail=caseDetail, caseAttach='N/A', user_id=current_user.id)
            print(new_case)
            db.session.add(new_case)
            db.session.commit()
            return redirect(url_for('views.text'))

        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            print(filename)
            print(os.path.join(CASE_PATH, filename))
            file.save(os.path.join(CASE_PATH, filename))
            new_case = Case(caseName=caseName, caseDetail=caseDetail, caseAttach=filename, user_id=current_user.id)
            print(new_case)
            db.session.add(new_case)
            db.session.commit()
            return redirect(url_for('views.test'))
    return render_template("test.html", user=current_user)
    

#@views.route('/case_add', methods=['POST'])
#def case_add():
#    if request.method == 'POST':
#        new_caseName = request.form.get('formCaseName')
#        new_caseDetail = request.form.get('formCaseDetail')
#        print(new_caseName, new_caseDetail)


#    return render_template("test.html", user=current_user)

@views.route('/delete-note', methods=['POST'])
def delete_note():
    note = json.loads(request.data)
    noteId = note['noteId']
    note = Note.query.get(noteId)

    if note:
        if note.user_id == current_user.id:
            db.session.delete(note)
            db.session.commit()
            return jsonify()

