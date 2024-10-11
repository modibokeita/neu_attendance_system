import unittest
from unittest.mock import patch, MagicMock
from app import dataset, update_attendance, generate_frame  # Adjust the import as necessary
import cv2
import numpy as np

class TestFunctions(unittest.TestCase):

    @patch('app.db_connection')
    @patch('app.cv2.imread')
    def test_dataset_success(self, mock_imread, mock_db_connection):
        # Set up the mock database cursor
        mock_cursor = MagicMock()
        mock_db_connection.cursor.return_value = mock_cursor

        # Sample student data
        student_id = 1
        mock_cursor.fetchone.return_value = {
            'id': student_id,
            'name': 'John Doe',
            'major': 'Computer Science',
            'attendance_time': None
        }
        mock_imread.return_value = 'mock_image'

        # Call the dataset function
        student_info, img_student, seconds_elapsed, current_time = dataset(student_id)

        # Assertions
        self.assertIsNotNone(student_info)
        self.assertEqual(student_info['name'], 'John Doe')
        self.assertEqual(img_student, 'mock_image')
        self.assertEqual(seconds_elapsed, 0)

    @patch('app.db_connection')
    def test_update_attendance_success(self, mock_db_connection):
        # Set up the mock database cursor
        mock_cursor = MagicMock()
        mock_db_connection.cursor.return_value = mock_cursor

        student_id = 1
        update_attendance(student_id)

        # Assertions
        mock_cursor.execute.assert_called_once()
        self.assertIn('UPDATE Students SET attendance_time =', mock_cursor.execute.call_args[0][0])

    @patch('app.cv2.VideoCapture')
    @patch('app.cv2.imencode')
    @patch('app.face_recognition.face_locations')
    @patch('app.face_recognition.face_encodings')
    @patch('app.pickle.load')
    def test_generate_frame(self, mock_load, mock_face_encodings, mock_face_locations, mock_imencode, mock_video_capture):
        # Mock the video capture
        mock_capture = MagicMock()
        mock_video_capture.return_value = mock_capture

        # Create a dummy numpy array to simulate a frame
        mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)  # Create a black frame
        mock_capture.read.return_value = (True, mock_frame)

        # Mock face recognition functions
        mock_face_locations.return_value = [(0, 0, 1, 1)]
        mock_face_encodings.return_value = ['mock_encoding']
        mock_load.return_value = (['mock_encoding'], [1])

        # Mock encoding of the image
        mock_imencode.return_value = (True, b'mock_encoded_image')  # Return bytes

        # Call generate_frame function
        frame_generator = generate_frame()
        frame = next(frame_generator)

        # Assertions
        # self.assertIn(b"--frame\r\n", frame)
        # self.assertIn(b"Content-Type: image/jpeg\r\n", frame)

if __name__ == "__main__":
    unittest.main()
