from flask import Flask, render_template, request, url_for, redirect, session
from flask_socketio import SocketIO, join_room, leave_room
from database import add_doctor,add_patient,get_user,verify_email,is_email_verified,account_exist,data_filled,add_patient_info,get_patient_data,get_patient_report,add_patient_report
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import math,random
from util_tools import gen_otp,send_mail
import os
#from dotenv import load_dotenv
from flask import Flask, render_template, request, abort
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VideoGrant, ChatGrant
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import datetime

#load_dotenv()
twilio_account_sid = "**"
twilio_api_key_sid = "**"
twilio_api_key_secret = "**"
twilio_client = Client(twilio_api_key_sid, twilio_api_key_secret,
					   twilio_account_sid)



def get_chatroom(name):
	for conversation in twilio_client.conversations.conversations.list():
		if conversation.friendly_name == name:
			return conversation

	# a conversation with the given name does not exist ==> create a new one
	return twilio_client.conversations.conversations.create(
		friendly_name=name)

app = Flask(__name__)
app.config['SECRET_KEY'] = '**'
socketio = SocketIO(app)
#app.secret_key = "**"
login_manager = LoginManager()
login_manager.login_view = 'home'
login_manager.init_app(app)


'''@app.route('/')
def splash():
	return render_template("splash_screen.html")'''


@app.route('/')
def home():
	if current_user.is_authenticated:
		if current_user.get_user_type() == 1:
			return redirect(url_for('patient'))
		if current_user.get_user_type() == 2:
			return redirect(url_for('doctor'))
		if current_user.get_user_type() == 3:
			return redirect(url_for('admin'))
	return render_template("home.html")


@app.route('/login', methods=["POST"])
def usr_login():
	error_msg = ""
	if request.method == "POST":
		user_name = request.form['uname']
		pswd = request.form['pswd']
		usr = get_user(user_name)
		print("Test print: ",usr)
		if usr and usr.check_password(pswd):
			login_user(usr,remember=True)
			print("Test print: ",usr)
			if current_user.get_user_type() == 1:
				return redirect(url_for('patient'))
			if current_user.get_user_type() == 2:
				return redirect(url_for('doctor'))
			if current_user.get_user_type() == 3:
				return redirect(url_for('admin'))
		return render_template("home.html", error_msg="Login failed!")

	return redirect(url_for("home"))



@app.route('/video_login', methods=['POST'])
def login():
	username = request.get_json(force=True).get('username')
	if not username:
		abort(401)

	conversation = get_chatroom('My Room')
	try:
		conversation.participants.create(identity=username)
	except TwilioRestException as exc:
		# do not error if the user is already in the conversation
		if exc.status != 409:
			raise

	token = AccessToken(twilio_account_sid, twilio_api_key_sid,
						twilio_api_key_secret, identity=username)
	token.add_grant(VideoGrant(room='My Room'))
	token.add_grant(ChatGrant(service_sid=conversation.chat_service_sid))

	return {'token': token.to_jwt().decode(),
			'conversation_sid': conversation.sid}



@app.route('/signup_pat', methods=["POST", "GET"])
def patient_register():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	if request.method == "POST":
		name = request.form.get('name')
		email = request.form.get('email')
		password = request.form.get('pswd')
		add = request.form.get('address')
		mob = request.form.get('phone')
		dob = request.form.get('dob')
		kyc = request.form.get('kyc')
		print(name, email, password, add, mob, dob, kyc)
		if account_exist(email):
			return render_template("patient_register.html", error_msg="Account already exists with this email!")
		add_patient(email, password, name, add, mob, dob, kyc)
		usr = get_user(email)
		print(usr)
		if usr and usr.check_password(password):
			login_user(usr, remember=True)
			return redirect(url_for('patient'))
	return render_template("patient_register.html")


@app.route('/patient', methods=["POST", "GET"])
@login_required
def patient():
	if not is_email_verified(current_user.get_id()):
		print("Redirecting to email verification")
		return redirect(url_for('verify'))
	print(current_user.is_record_filled())
	if not current_user.is_record_filled():
		if not data_filled(current_user.get_id()):
			return redirect(url_for("caseHistory"))
	return render_template("patient_profile.html")

 
@app.route('/signup_doc',methods=["POST","GET"])
def doctor_register():
	# if current_user.get_user_type == 3:
		# print("yes")
	if request.method == "POST":
		name = request.form.get('name')
		doc_reg = request.form.get('doc_reg')
		email = request.form.get('email')
		password = request.form.get('pswd')
		add = request.form.get('address')
		country = request.form.get('country')
		state = request.form.get('state')
		mob = request.form.get('phone')
		dob = request.form.get('dob')
		kyc = request.form.get('kyc')
		print(name,doc_reg,email,password,add,country,state,mob,dob,kyc)
		add_doctor(doc_reg,email,password,name,add,country,state,mob,dob,kyc)
	return render_template("doctoor_registration.html")    


@app.route('/doctor',methods=["GET"])
@login_required
def doctor():
	if not is_email_verified(current_user.get_id()):
		print("Redirecting to email verification")
		return redirect(url_for('verify'))
	return render_template("doctor_profile.html")


@app.route('/admin',methods=["POST","GET"])
@login_required
def admin():
	if request.method=="POST":
		return redirect(url_for('doctor_register'))
	return render_template("admin.html")


@app.route('/verify',methods=['GET','POST'])
@login_required
def verify():
	#print(session)
	if request.method == 'POST' and 'otp' in session:
		otp1=request.form.get("otp")
		print(otp1, ' | ', session['otp'])
		if session['otp'] == otp1:
			verify_email(current_user.get_id())
			return redirect(url_for('home'))
		return render_template('otp_ver.html',error_msg = "Otp verification failed")
	if not current_user.is_verified():
		otp = gen_otp()
		session['otp'] = otp
		print("Session :- ",session)
		send_mail(current_user.get_id(),otp)
		return render_template('otp_ver.html')
	return redirect(url_for('home'))


@app.route('/medical_history',methods=['GET','POST'])
@login_required
def caseHistory():
	if request.method == 'POST':
		ans = request.get_json(force=True)
		print(ans)
		add_patient_info(current_user.get_id(),ans)
		return redirect(url_for("patient"))
	return render_template("case_history_bot.html")


@app.route('/doc_medic_history/<pat_id>',methods=['GET','POST'])
@login_required
def doc_data(pat_id):
	if current_user.get_user_type() == 2:
		info = get_patient_data(pat_id)['data']
		info2 = get_patient_report(pat_id)
		if not info2:
			info2 =''
		return render_template('patient_info.html',pat_info=info,pat_info2=info2)
	return "<h1>Not Authorised"



@app.route('/my_info')
@login_required
def pat_info():
	info = get_patient_data(current_user.get_id())['data']
	info2 = get_patient_report(current_user.get_id())
	if not info2:
		info2 =''
	return render_template('patient_info.html',pat_info=info,pat_info2=info2)

@app.route("/logout/")
@login_required
def logout():
	logout_user()
	return redirect(url_for('home'))


@app.route("/order_meds")
def order():
	return render_template("order_meds.html")


@app.route("/chat")
@login_required
def chat():
	name = current_user.get_id()
	group_name = name
	return render_template("consult_bot.html",name = name,group_name=group_name)

@app.route("/doc_chat/<pat_id>")
@login_required
def docchat(pat_id):
	name = "Doctor"
	group_name = pat_id
	return render_template("consult_bot.html",name = name,group_name=group_name)

@app.route("/doc_report/<pat_id>",methods=['GET','POST'])
@login_required
def report(pat_id):
	if current_user.get_user_type() ==2:
		if request.method == "POST":
			res = list(request.form.values())
			brief = res[0]
			medicine = res[1:]
			date_t = str(datetime.date.today())
			add_patient_report({'date':date_t,'doc_id':current_user.get_id(),'pat_id':pat_id,'remark':brief,'medicine':medicine})

			print(res)
			return redirect(url_for("doctor"))
		return render_template("report.html")
	return "<h1>Not Authorised</h1>"


@login_manager.user_loader
def load_user(username):
	return get_user(username)


@socketio.on('admin_joined')
def join_admin(data):
	print("Admin  Joined ",data)
	join_room(data['room'])


@socketio.on('join_room')
def joined(data,methods=['GET','POST']):
	print(current_user.get_id(), data)
	print("{} has joind the room {}".format(data['username'],data['room']))
	#p = get_message(data['room'],100)
	#print(p)
	join_room(data['room'])
	#socketio.emit("joined", data)
	socketio.emit('joined',data, room = data['room'])

@socketio.on('send')
def handle_my_custom_event(json, methods=['GET', 'POST']):
	print('received my event: ' + str(json))
	json['img'] = url_for('static',filename='logo.png')
	#try:
		#save_message(json['room'],json['message'],json['username'])
	#except:
		#pass
	if json['username'] == 'Admin':
		socketio.emit('receive', json)
	else:
		socketio.emit('receive', json,room= json['room'])
	if json['message'][0:3].lower() == 'ans':
		socketio.emit('receive', json, room = "Admin")

@socketio.on('leave_room')
def handle_leave_room_event(data):
	#app.logger.info("{} has left the room {}".format(data['username'], data['room']))
	leave_room(data['room'])
	socketio.emit('left', data, room=data['room'])













if __name__ == '__main__':
	socketio.run(app, debug=True)
	#app.run(debug=True)
