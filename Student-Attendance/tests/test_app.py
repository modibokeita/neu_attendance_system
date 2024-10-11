import unittest

from app import app, db_connection


class TestApp(unittest.TestCase):

    def setUp(self):
        # Setup test client for Flask app
        self.app = app.test_client()
        self.app.testing = True

    def test_index_route(self):
        # Test the index route
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Attendance System', response.data)  # Check if content is present

    def test_video_route(self):
        # Test the video route
        response = self.app.get('/video')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'multipart/x-mixed-replace; boundary=frame')


    def test_student_attendance_list(self):
        response = self.app.get('/student_attendance_list')  # Use the correct route
        self.assertEqual(response.status_code, 200)  # Ensure the request was successful
        # self.assertIn(b"Student Attendance List", response.data)  # Check for specific content


    # def tearDown(self):
    #     # Clean up the database after each test
    #     cursor = db_connection.cursor()
    #     cursor.execute("DELETE FROM StudentImages")  # Clear test data from StudentImages table
    #     cursor.execute("DELETE FROM Students")  # Clear test data from Students table
    #     db_connection.commit()
    #     cursor.close()

if __name__ == "__main__":
    unittest.main()
