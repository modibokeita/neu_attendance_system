from flask import Flask, render_template, Response, redirect, url_for, request, flash, jsonify, send_file, session, current_app
import cv2
import csv
from reportlab.lib import colors
import os
import pickle
import face_recognition
import numpy as np
import cvzone
import json
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
import mysql.connector  # New import for MySQL connection
from settings.initial_encoder import initialize_student_data

# Flask app initialization
app = Flask(__name__)
app.secret_key = '24425d9a564c8eada45620220600da20'
initialize_student_data()

# MySQL database connection with error handling
try:
    db_connection = mysql.connector.connect(
        host="localhost",
        user="root",         # Replace with your MySQL user
        password="Keita@1234",  # Replace with your MySQL password
        database="aiiovdft_profdux"  # Replace with your database name
    )
    print("Connection to MySQL DB successful App")
    db_cursor = db_connection.cursor(dictionary=True)
except mysql.connector.Error as err:
    print(f"Error: {err}")
    db_connection, db_cursor = None, None  # Ensure program doesn't crash


def dataset(id):
    """
    Fetch student dataset from MySQL
    """
    try:
        # Create a new cursor for this function
        db_cursor = db_connection.cursor(dictionary=True)

        # Query to fetch student data
        query = "SELECT * FROM Students WHERE id = %s"
        db_cursor.execute(query, (id,))
        studentInfo = db_cursor.fetchone()  # Fetch student data

        if not studentInfo:
            print(f"No data found for student ID: {id}")
            db_cursor.close()
            return None, None, None, None  # Return None if no data is found

        # Load student image
        img_path = f"./static/Files/Images/{id}.png"  # Path to the student image
        imgStudent = cv2.imread(img_path)
        if imgStudent is None:
            print(f"Could not load image for student ID: {id}")

        # Handle attendance time and last attendance date
        last_attendance_time = studentInfo.get("attendance_time")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Get current time

        if last_attendance_time is None:
            print(f"Attendance time is missing for student ID: {id}")

            secondElapsed = 0
        else:
            # If attendance time exists, process it
            if isinstance(last_attendance_time, datetime):
                datetimeObject = last_attendance_time
            else:
                # Convert to datetime if it's a date object
                datetimeObject = datetime.combine(last_attendance_time, datetime.min.time())

            secondElapsed = (datetime.now() - datetimeObject).total_seconds()

        db_cursor.close()  # Close the cursor after fetching data

        return studentInfo, imgStudent, secondElapsed, current_time
    except mysql.connector.Error as e:
        print(f"Error fetching dataset for student ID {id}: {e}")
        return None, None, None, None


def update_attendance(id):
    """
    Update student attendance in MySQL
    """
    try:
        # Create a new cursor for this function
        db_cursor = db_connection.cursor()

        query = "UPDATE Students SET attendance_time = %s WHERE id = %s"
        attendance_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_cursor.execute(query, (attendance_time, id))
        db_connection.commit()
        db_cursor.close()  # Close the cursor after updating
    except mysql.connector.Error as e:
        print(f"Error updating attendance for student ID {id}: {e}")

# Background task for video frame generation and face recognition
already_marked_id_student = []
already_marked_id_admin = []


def generate_frame(student_id):
    try:
        capture = cv2.VideoCapture(0)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        imgBackground = cv2.imread("static/Files/Resources/background.png")
        folderModePath = "static/Files/Resources/Modes/"
        modePathList = os.listdir(folderModePath)
        imgModeList = [cv2.imread(os.path.join(folderModePath, path)) for path in modePathList]

        modeType = 0
        id = -1
        imgStudent = []
        counter = 0

        with open("EncodeFile.p", "rb") as file:
            encodeListKnownWithIds = pickle.load(file)
        encodedFaceKnown, studentIDs = encodeListKnownWithIds

        while True:
            success, img = capture.read()
            if not success:
                break
            else:
                imgSmall = cv2.resize(img, (0, 0), None, 0.25, 0.25)
                imgSmall = cv2.cvtColor(imgSmall, cv2.COLOR_BGR2RGB)

                faceCurrentFrame = face_recognition.face_locations(imgSmall)
                encodeCurrentFrame = face_recognition.face_encodings(imgSmall, faceCurrentFrame)

                imgBackground[162:162 + 480, 55:55 + 640] = img
                imgBackground[44:44 + 633, 808:808 + 414] = imgModeList[modeType]

                if faceCurrentFrame:
                    for encodeFace, faceLocation in zip(encodeCurrentFrame, faceCurrentFrame):
                        try:
                            matches = face_recognition.compare_faces(encodedFaceKnown, encodeFace)
                            faceDistance = face_recognition.face_distance(encodedFaceKnown, encodeFace)
                            matchIndex = np.argmin(faceDistance)

                            y1, x2, y2, x1 = faceLocation
                            y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4

                            bbox = 55 + x1, 162 + y1, x2 - x1, y2 - y1
                            imgBackground = cvzone.cornerRect(imgBackground, bbox, rt=0)

                            if matches[matchIndex]:
                                id = studentIDs[matchIndex]
                                if counter == 0:
                                    cvzone.putTextRect(imgBackground, "Face Detected", (65, 200), thickness=2)
                                    counter = 1
                                    modeType = 1
                            else:
                                cvzone.putTextRect(imgBackground, "Face Not Found", (65, 200), thickness=2)
                                modeType = 4
                                counter = 0
                                imgBackground[44:44 + 633, 808:808 + 414] = imgModeList[modeType]

                                # Save image when face is not found
                                image_path = f"static/Files/Cheaters/not_found_image_{student_id}.png"
                                cv2.imwrite(image_path, img)  # Save the image

                                # Save student info in the database
                                student_name = "Unknown"  # Replace with actual name if available
                                save_student_info_to_db(student_id, student_name, image_path)

                        except Exception as e:
                            print(f"Error processing face recognition: {e}")

                if counter != 0:
                    if counter == 1:
                        studentInfo, imgStudent, secondElapsed, current_time = dataset(id)
                        if secondElapsed > 60:
                            update_attendance(id)
                            already_marked_id_student.append(id)
                            already_marked_id_admin.append(id)
                        else:
                            modeType = 3
                            counter = 0

                    if modeType != 3:
                        if 5 < counter <= 10:
                            modeType = 2

                        imgBackground[44:44 + 633, 808:808 + 414] = imgModeList[modeType]
                        if counter <= 5:
                            cv2.putText(imgBackground, str(studentInfo["name"]), (808 + 100, 445), cv2.FONT_HERSHEY_COMPLEX, 1, (50, 50, 50), 1)
                            imgStudentResize = cv2.resize(imgStudent, (216, 216))
                            imgBackground[175:175 + 216, 909:909 + 216] = imgStudentResize

                        counter += 1
                        if counter >= 10:
                            counter = 0
                            modeType = 0
                            studentInfo = []
                            imgStudent = []
                else:
                    modeType = 0
                    counter = 0

            ret, buffer = cv2.imencode(".jpeg", imgBackground)
            frame = buffer.tobytes()

            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    except Exception as e:
        print(f"Error in generate_frame: {e}")
        yield b""



def save_student_info_to_db(student_id, student_name, image_path):
    try:
        db_cursor = db_connection.cursor()

        # Check if the student_id already exists
        db_cursor.execute("SELECT COUNT(*) FROM Cheat WHERE student_id = %s", (student_id,))
        exists = db_cursor.fetchone()[0]

        if exists:
            # Update the existing record
            query = "UPDATE Cheat SET student_name = %s, face_image = %s WHERE student_id = %s"
            db_cursor.execute(query, (student_name, image_path, student_id))
            print(f"Record for student ID {student_id} updated successfully.")
        else:
            # Insert a new record
            query = "INSERT INTO Cheat (student_id, student_name, face_image) VALUES (%s, %s, %s)"
            db_cursor.execute(query, (student_id, student_name, image_path))
            print("Data saved successfully!")

        # Commit the changes to the database
        db_connection.commit()
        db_cursor.close()
    except Exception as e:
        print(f"Error saving to database: {e}")





# Flask routes
@app.route("/index")
def index():
    try:
        student_id = session.get('student_id', 'Unknown')
        # You can check for a session or a login status here
        if 'student_logged_in' not in session:
            return redirect(url_for("student_login"))  # Redirect to login if not logged in
        return render_template("index.html", student_id=student_id)
    except Exception as e:
        return f"Error rendering index: {e}"


@app.route("/video/<student_id>")
def video(student_id):
    try:

        return Response(generate_frame(student_id), mimetype="multipart/x-mixed-replace; boundary=frame")
    except Exception as e:
        return f"Error streaming video: {e}"

# @app.route("/student_attendance_list")
# def student_attendance_list():
#     try:
#         unique_id_student = list(set(already_marked_id_student))
#         student_info = [dataset(i) for i in unique_id_student]

#         attendance_data = []
#         csv_file_path = './static/Files/attendance_list.csv'

#         with open(csv_file_path, mode='w', newline='') as csv_file:
#             fieldnames = ['ID', 'Name', 'Major', 'Attendance Time']
#             writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
#             writer.writeheader()

#             for student in student_info:
#                 student_data = student[0]  # Extract student info
#                 student_attendance_time = student_data['attendance_time']   # Format current time

#                 attendance_data.append({
#                     'student_id': student_data['id'],
#                     'name': student_data['name'],
#                     'major': student_data['major'],
#                     'attendance_time': student_attendance_time,
#                 })

#                 writer.writerow({
#                     'ID': student_data['id'],
#                     'Name': student_data['name'],
#                     'Major': student_data['major'],
#                     'Attendance Time': student_attendance_time,
#                 })

#         return render_template("student_attendance_list.html", data=attendance_data)
#     except Exception as e:
#         return f"Error generating student attendance list: {e}"


@app.route("/student_attendance_list")
def student_attendance_list():
    try:
        unique_id_student = list(set(already_marked_id_student))
        student_info = [dataset(i) for i in unique_id_student]

        attendance_data = []
        current_time = datetime.now()  # Capture the current timestamp for reference

        # Create a PDF object using BytesIO
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setTitle("Attendance List")
        c.setFont("Helvetica", 12)

        logo_path = './static/Files/Neu.jpeg'
        c.drawImage(logo_path, 10, 680, width=100, height=50)

        # Title for the PDF
        c.drawString(110, 700, "NEAR EAST UNIVERSITY")
        c.drawString(110, 685, "INTERNATIONAL RESEARCH CENTER FOR AI AND AIOT")
        c.drawString(110, 670, f"Student Attendance List - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Table headers
        dark_red = colors.Color(0.267, 0.012, 0.012)
        c.setFillColor(dark_red)
        c.rect(50, 640, 500, 20, fill=True)
        c.setFillColor(colors.whitesmoke)
        c.drawString(50, 645, "ID")
        c.drawString(150, 645, "Name")
        c.drawString(300, 645, "Major")
        c.drawString(450, 645, "Attendance Time")
        c.setFillColor(colors.black)

        y = 620

        # Populate the PDF with student data
        for student in student_info:
            student_data = student[0]
            student_attendance_time = student_data['attendance_time']

            # Convert attendance_time from datetime to string
            if isinstance(student_attendance_time, datetime):
                student_attendance_time = student_attendance_time.strftime('%Y-%m-%d %H:%M:%S')

            attendance_data.append({
                'student_id': student_data['id'],
                'name': student_data['name'],
                'major': student_data['major'],
                'attendance_time': student_attendance_time,
            })

            # Write student data to the PDF
            c.drawString(50, y, str(student_data['id']))
            c.drawString(150, y, student_data['name'])
            c.drawString(300, y, student_data['major'])
            c.drawString(450, y, student_attendance_time)

            y -= 20

            if y < 50:
                c.showPage()
                y = 750

        # Save the PDF to the buffer
        c.save()

        buffer.seek(0)

        return send_file(buffer, as_attachment=True, download_name="attendance_list.pdf", mimetype='application/pdf')
    except Exception as e:
        return f"Error generating student attendance list: {e}"

@app.route('/admin/', methods=['GET', 'POST'])
def admin():
    return render_template("admin_login.html")


@app.route('/admin/cheaters')
def display_cheaters():
    try:
        # Establish a connection to the MySQL database
        db_cursor = db_connection.cursor()

        # Execute the query to retrieve all cheaters from the 'Cheat' table
        db_cursor.execute("SELECT student_id, student_name, face_image FROM Cheat")
        cheaters = db_cursor.fetchall()  # Fetch all results

        # Close the cursor
        db_cursor.close()

        # Pass the list of cheaters to the 'heater.html' template
        return render_template('heater.html', cheaters=cheaters)
    except Exception as e:
        return f"Error fetching cheaters: {e}"


@app.route("/", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        id_number = request.form.get("id_number", False)
        email = request.form.get("email", False)
        password = request.form.get("password", False)

        # Fetch student data from the database for validation
        student_info = fetch_student_by_id(id_number)

        if student_info:
            # Check the credentials
            if (
                student_info['password'] == password
                and student_info['email'] == email
            ):
                # Set session to indicate the student is logged in
                session['student_logged_in'] = True
                session['student_id'] = id_number  # Optional: store the student's ID in the session

                return redirect(url_for("index"))  # Redirect to the home page
            else:
                return render_template("student_login.html", data=" ❌ Email/Password Incorrect")
        else:
            return render_template("student_login.html", data=" ❌ The ID is not registered")

    return render_template("student_login.html")


def fetch_student_by_id(student_id):
    try:
        db_cursor = db_connection.cursor()
        query = "SELECT * FROM Students WHERE id = %s"
        db_cursor.execute(query, (student_id,))
        result = db_cursor.fetchone()
        db_cursor.close()

        if result:
            # Assuming the columns in Students table are in this order:
            # id, name, password, email, major, attendance_time
            return {
                'id': result[0],
                'name': result[1],
                'password': result[2],
                'email': result[3],
                'major': result[4],
                'attendance_time': result[5]
            }
        else:
            return None
    except Exception as e:
        print(f"Error fetching student by ID: {e}")
        return None




@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        id_number = request.form.get("id_number", False)
        email = request.form.get("email", False)
        password = request.form.get("password", False)

        # Fetch student IDs from the database for validation
        studentIDs = [student['id'] for student in fetch_all_students()]

        if id_number:
            if id_number not in studentIDs:
                return render_template("admin_login.html", data=" ❌ The ID is not registered")
            else:
                # Check admin credentials in the MySQL database
                student_info = dataset(id_number)  # This retrieves student info from MySQL
                if student_info:
                    # Assuming 'student_info' returns a dictionary containing the student data
                    if (
                        student_info[0]["password"] == password
                        and student_info[0]["email"] == email
                    ):
                        return redirect(url_for("admin_dashboard"))
                    else:
                        return render_template("admin_login.html", data=" ❌ Email/Password Incorrect")
                else:
                    return render_template("admin_login.html", data=" ❌ No data found for the given ID")
        else:
            return render_template("admin_login.html")

    return render_template("admin_login.html")

def fetch_all_students():
    """
    Fetch all student IDs from MySQL
    """
    try:
        db_cursor = db_connection.cursor(dictionary=True)
        query = "SELECT id FROM Students"
        db_cursor.execute(query)
        return db_cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error fetching student IDs: {err}")
        return []

@app.route("/admin_dashboard")
def admin_dashboard():
    # Create a cursor to interact with the database
    db_cursor = db_connection.cursor(dictionary=True)  # Use dictionary=True for named results

    # Query to fetch student data
    query = "SELECT id, name, major, email, attendance_time FROM Students"
    db_cursor.execute(query)

    # Fetch all results as dictionaries
    data = db_cursor.fetchall()

    # Close the cursor after fetching data
    db_cursor.close()

    current_year = datetime.now().year
    # Render the admin dashboard with student data
    return render_template('admin_dashboard.html', data=data, current_year=current_year)

# Error handling
@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

@app.route("/admin/add_user", methods=["GET", "POST"])
def add_user():
    if request.method == "POST":
        id = request.form.get("id", False)
        name = request.form.get("name", False)
        password = request.form.get("password", False)
        email = request.form.get("email", False)
        major = request.form.get("major", False)

        # Save the uploaded image
        image = request.files.get("image")
        if image:
            image_path = f"./static/Files/Images/{id}.png"
            image.save(os.path.join(image_path))

            # Extract face encodings from the image
            img = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(img)

            if face_encodings:  # Check if any face encodings were found
                face_encoding = face_encodings[0]  # Get the first encoding
            else:
                flash("No face found in the image. Please upload a clear image.", "danger")
                return redirect(url_for("add_user"))

            # Convert the encoding to binary format for storage in MySQL
            face_encoding_blob = face_encoding.tobytes()  # Convert to bytes

            # Insert data into MySQL database for the student
            try:
                add_student_query = """
                INSERT INTO Students (id, name, password, email, major, attendance_time)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                student_data = (id, name, password, email, major, None)  # Set attendance_time to None
                db_cursor.execute(add_student_query, student_data)

                # Now insert the image and encoding into StudentImages table
                add_image_query = """
                INSERT INTO StudentImages (student_id, image_path, face_encoding)
                VALUES (%s, %s, %s)
                """
                image_data = (id, image_path, face_encoding_blob)
                db_cursor.execute(add_image_query, image_data)

                db_connection.commit()  # Commit changes
                flash("User added successfully!", "success")
            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")
                db_connection.rollback()  # Rollback in case of error

        return redirect(url_for("add_user"))  # Redirect after POST to avoid resubmission

    return render_template("add_user.html")  # Create this template for the form


@app.route("/admin/edit_user", methods=["POST", "GET"])
def edit_user():
    value = request.form.get("edit_student")

    # Fetch student data, image, and time elapsed from dataset function
    studentInfo, imgStudent, secondElapsed, current_time = dataset(value)

    # Handle case where studentInfo is None (if no student is found)
    if studentInfo is None:
        return "Student not found", 404

    # Calculate hours elapsed since last attendance
    hoursElapsed = round((secondElapsed / 3600), 2)

    # Prepare the data to pass to the template
    info = {
        "studentInfo": studentInfo,  # Contains student's details like id, name, email, major
        "lastlogin": hoursElapsed,   # Hours since the last attendance was recorded
        "image": imgStudent,         # Path to student's image
    }

    # Render the template with the student's data
    return render_template("edit_user.html", data=info)

@app.route("/admin/save_changes", methods=["POST"])
def save_changes():
    content = request.get_data()

    # Convert the received data into a dictionary and strip any unnecessary whitespace
    dic_data = json.loads(content.decode("utf-8"))
    dic_data = {k: v.strip() for k, v in dic_data.items()}

    # Ensure data types are properly converted (adjust as per your schema)
    dic_data["id"] = int(dic_data["id"])  # Assuming `id` is an integer

    # Update query for the MySQL `Students` table
    query = """
        UPDATE Students
        SET
            name = %s,
            email = %s,
            major = %s,
            password = %s
        WHERE id = %s
    """

    # Define the parameters for the query
    values = (
        dic_data["name"],
        dic_data["email"],
        dic_data["major"],
        dic_data["password"],
        dic_data["id"],
    )

    try:
        # Execute the update in the database
        db_cursor = db_connection.cursor(dictionary=True)
        db_cursor.execute(query, values)
        db_connection.commit()
        db_cursor.close()

        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        # Handle any errors that occur during the update
        print(f"Error updating data: {str(e)}")
        return jsonify({"error": f"Failed to update data: {str(e)}"}), 500

def delete_image(student_id):
    # Define the path to the student's image file
    filepath = f"./static/Files/Images/{student_id}.png"

    # Check if the file exists before trying to remove it
    if os.path.exists(filepath):
        try:
            os.remove(filepath)  # Remove the local image file
            return "Image deleted successfully!"
        except Exception as e:
            print(f"Error deleting image: {str(e)}")
            return f"Failed to delete image: {str(e)}"
    else:
        return "Image file not found."

def add_image_database():
    """
    Fetch all student IDs and their corresponding images from MySQL.
    """
    try:
        db_cursor = db_connection.cursor(dictionary=True)
        query = "SELECT id, image_path FROM StudentImages"
        db_cursor.execute(query)
        results = db_cursor.fetchall()

        studentIDs = []
        imgList = []

        for result in results:
            student_id = result['id']
            image_path = result['image_path']
            studentIDs.append(student_id)

            # Load the image only if the path is valid
            if image_path and os.path.isfile(image_path):
                img = cv2.imread(image_path)
                if img is not None:
                    imgList.append(img)
                else:
                    print(f"Could not load image at path: {image_path}")
            else:
                print(f"Invalid image path: {image_path}")

        db_cursor.close()
        return studentIDs, imgList

    except mysql.connector.Error as err:
        print(f"Error fetching images from database: {err}")
        return [], []  # Return empty lists in case of error



def findEncodings(imgList):
    """
    Find face encodings for the list of images.
    """
    encodeList = []
    for img in imgList:
        # Convert the image from BGR to RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Find face encodings
        encode = face_recognition.face_encodings(img_rgb)
        if encode:
            encodeList.append(encode[0])  # Append the first encoding found
        else:
            print("No face encodings found in the image.")

    return encodeList


@app.route("/admin/delete_user", methods=["POST"])
def delete_user():
    content = request.get_data()

    # Load the student_id from the received JSON data
    student_id = json.loads(content.decode("utf-8"))
    student_id = student_id.strip()  # Ensure no extra whitespace

    try:
        # First, delete any associated images from the StudentImages table
        delete_images_query = "DELETE FROM StudentImages WHERE student_id = %s"
        db_cursor = db_connection.cursor(dictionary=True)
        db_cursor.execute(delete_images_query, (student_id,))

        # Now, delete the student from the Students table
        delete_student_query = "DELETE FROM Students WHERE id = %s"
        db_cursor.execute(delete_student_query, (student_id,))

        # Commit the transaction directly on the connection object
        db_connection.commit()

        # Optionally, update encoding file (if needed)
        studentIDs, imgList = add_image_database()  # Ensure this function is defined
        encodeListKnown = findEncodings(imgList)  # Ensure this function is defined
        encodeListKnownWithIds = [encodeListKnown, studentIDs]

        # Save the updated encodings to a file
        with open("EncodeFile.p", "wb") as file:
            pickle.dump(encodeListKnownWithIds, file)

        db_cursor.close()
        return "User deleted successfully!", 200
    except Exception as e:
        # Handle errors during the delete operation
        print(f"Error deleting user: {str(e)}")
        return f"Failed to delete user: {str(e)}", 500




if __name__ == "__main__":
    app.run(debug=True)
