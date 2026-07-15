from flask import Blueprint, render_template, flash, request, jsonify, redirect, url_for, send_from_directory
from flask_login import login_required, current_user
import pandas
import json
from .models import Note, User, Case
from . import db, UPLOAD_FOLDER
from werkzeug.utils import secure_filename
import os
from datetime import datetime

views = Blueprint('views', __name__)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
CURR_DIR = current_directory = os.path.dirname(os.path.abspath(__file__))
CASE_PATH = os.path.join(CURR_DIR, UPLOAD_FOLDER)
print(CURR_DIR)
print(CASE_PATH)

@views.route('/cases/<path:filename>')
def serve_case_file(filename):
    cases_dir = os.path.join(CURR_DIR, UPLOAD_FOLDER)
    return send_from_directory(cases_dir, filename)

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

@views.route('/case_view', methods=['GET', 'POST'])
@login_required
def case_view():
    return render_template('case_display.html', user=current_user)

@views.route('/case_add', methods=['GET', 'POST'])
def case_add():
    if request.method == 'POST':
        caseFirstName = request.form.get('formFirstName')
        caseSurname = request.form.get('formSurname')
        
        # Convert the date string to a datetime object
        dob_parts = request.form['dob'].split('-')  # Use '-' for correct date format splitting
        day, month, year = int(dob_parts[2]), int(dob_parts[1]), int(dob_parts[0])
        caseDOB = datetime(year, month, day)
        
        caseGender = request.form.get('formGender')
        casePhoneNum = request.form.get('formPhoneNum')
        caseCaseDetail = request.form.get('formCaseDetail')
        CaseNotes = request.form.get('formCaseNotes')
        casePhysDesc = request.form.get('formPhysDesc')
        
        # check if the post request has the file part
        if 'file' not in request.files:
            new_case = Case(caseFirstName=caseFirstName, caseSurname=caseSurname, caseDOB=caseDOB, caseGender=caseGender, casePhoneNum=casePhoneNum, caseLocation=caseCaseDetail, caseNotes=CaseNotes, casePhysDesc=casePhysDesc, caseAttach="N/A", user_id=current_user.id)
            print(new_case)
            db.session.add(new_case)
            db.session.commit()
            flash('Case added!', category='success')
            return redirect(url_for('views.case_add'))

        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            print(filename)
            print(os.path.join(CASE_PATH, filename))
            file.save(os.path.join(CASE_PATH, filename))
            new_case = Case(caseFirstName=caseFirstName, caseSurname=caseSurname, caseDOB=caseDOB, caseGender=caseGender, casePhoneNum=casePhoneNum, caseLocation=caseCaseDetail, caseNotes=CaseNotes, casePhysDesc=casePhysDesc, caseAttach=filename, user_id=current_user.id)
            print(new_case)
            db.session.add(new_case)
            db.session.commit()
            flash('Case added!', category='success')
            return redirect(url_for('views.case_add'))
    return render_template("case_add.html", user=current_user)
    

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

