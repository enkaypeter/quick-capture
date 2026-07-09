from flask import Blueprint, render_template, flash, request, jsonify
from flask_login import login_required, current_user
import pandas
import json
from .models import Note, User, Case
from . import db, UPLOAD_FOLDER

views = Blueprint('views', __name__)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'py'}

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

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('download_file', name=filename))
    return '''

@views.route('/case_add', methods=['POST'])
def case_add():
    if request.method == 'POST':
        new_caseName = request.form.get('formCaseName')
        new_caseDetail = request.form.get('formCaseDetail')
        print(new_caseName, new_caseDetail)


    return render_template("test.html", user=current_user)

@views.route('/test', methods=['GET', 'POST'])
def test():
    if request.method == 'POST':
        new_caseName = request.form.get('formCaseName')
        new_caseDetail = request.form.get('formCaseDetail')
        print(new_caseName, new_caseDetail)

        #if len(new_caseName) < 1:
         #   flash('Case name is too short!', category='error')
        #elif new_caseDetail < 5:
          #  flash('Case detail section is too short!', category='error')
       # else:
            #new_case = Case(caseName=new_caseName, caseDetail=new_caseDetail, caseAttach=new_caseAttach, user_id=current_user.id)
            #db.session.add(new_note)
            #db.session.commit()
            #flash('Note added!', category='success')
    return render_template("test.html", user=current_user)

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

