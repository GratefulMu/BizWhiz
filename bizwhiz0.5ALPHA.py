import sys
import os
import json
import requests
from bs4 import BeautifulSoup
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QTableWidget, QTableWidgetItem, QInputDialog, QComboBox
from PyQt5.QtGui import QColor

class BusinessFinderApp(QWidget):
    def __init__(self):
        super().__init__()

        self.api_key = self.get_api_key()  # Prompt the user for API key
        self.results_file = 'businesses_results.json'
        self.saved_results = []  # Initialize saved_results list
        self.load_results()

        self.init_ui()

    def get_api_key(self):
        api_key, ok = QInputDialog.getText(self, 'API Key', 'Enter your Google Maps API key:')
        if not ok:
            sys.exit()  # User canceled, exit the application
        return api_key

    def load_results(self):
        if os.path.exists(self.results_file):
            with open(self.results_file, 'r') as file:
                try:
                    self.saved_results = json.load(file)
                except json.JSONDecodeError:
                    self.saved_results = []
        else:
            self.saved_results = []

    def save_results(self):
        with open(self.results_file, 'w') as file:
            json.dump(self.saved_results, file)

    def get_coordinates(self, zip_code):
        geocoding_url = f'https://maps.googleapis.com/maps/api/geocode/json?address={zip_code}&key={self.api_key}'
        response = requests.get(geocoding_url)
        data = response.json()

        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng']
        else:
            raise Exception(f"Failed to get coordinates for zip code {zip_code}. Error: {data.get('error_message')}")

    def get_place_details(self, place_id):
        details_url = f'https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,website,formatted_phone_number,formatted_address&key={self.api_key}'
        response = requests.get(details_url)
        data = response.json()

        if data['status'] == 'OK':
            return data['result']
        else:
            raise Exception(f"Failed to get place details. Error: {data.get('error_message')}")

    def find_email_on_website(self, website):
        try:
            response = requests.get(website)
            soup = BeautifulSoup(response.text, 'html.parser')

            email_addresses = set()
            for email_link in soup.select('a[href^="mailto:"]'):
                email_addresses.add(email_link.get('href').replace('mailto:', '').strip())

            return email_addresses
        except Exception as e:
            print(f"Error while scraping website: {e}")
            return set()

    def init_ui(self):
        self.setWindowTitle('BizWhiz')
        self.setGeometry(100, 100, 800, 600)  # Set a larger size

        self.label_zip = QLabel('Enter a zip code:')
        self.label_radius = QLabel('Enter the search radius in miles:')
        self.label_business_type = QLabel("Enter the type of business you're looking for:")

        self.entry_zip = QLineEdit()
        self.entry_radius = QLineEdit()
        self.entry_business_type = QLineEdit()

        self.search_button = QPushButton('Search')
        self.search_button.clicked.connect(self.search_button_clicked)

        self.result_table = QTableWidget()

        layout = QVBoxLayout()
        layout.addWidget(self.label_zip)
        layout.addWidget(self.entry_zip)
        layout.addWidget(self.label_radius)
        layout.addWidget(self.entry_radius)
        layout.addWidget(self.label_business_type)
        layout.addWidget(self.entry_business_type)
        layout.addWidget(self.search_button)
        layout.addWidget(self.result_table)

        self.setLayout(layout)

        # Display the last saved results
        self.display_saved_results()

    def display_saved_results(self):
        if self.saved_results:
            self.result_table.clear()

            # Set column headers
            self.result_table.setColumnCount(6)
            self.result_table.setHorizontalHeaderLabels(["Name", "Website", "Phone", "Emails", "Street Address", "Status"])

            # Enable sorting for columns
            self.result_table.setSortingEnabled(True)

            for saved_result in self.saved_results:
                # Display data in separate columns
                row_position = self.result_table.rowCount()
                self.result_table.insertRow(row_position)

                for col, value in enumerate(saved_result.values()):
                    self.result_table.setItem(row_position, col, QTableWidgetItem(value))

                # Create a combo box for the status
                status_combobox = QComboBox()
                status_combobox.addItems(["Not Contacted", "Contacted", "Signed-up", "Declined Services"])
                status_combobox.setCurrentText(saved_result["Status"])  # Set the status
                self.result_table.setCellWidget(row_position, 5, status_combobox)

                # Connect the combobox signal to a slot
                status_combobox.currentIndexChanged.connect(lambda _, row=row_position: self.status_changed(row))

                # Set background color based on status
                status = status_combobox.currentText()
                self.set_status_background_color(row_position, status)

            # Auto-adjust column width based on content length
            self.result_table.resizeColumnsToContents()

    def search_button_clicked(self):
        zip_code = self.entry_zip.text()
        miles = float(self.entry_radius.text())
        meters_radius = miles * 1609.34
        business_type = self.entry_business_type.text()

        try:
            location = self.get_coordinates(zip_code)
            businesses = self.search_nearby_businesses(location, meters_radius, business_type)

            self.saved_results = []  # Clear previous results
            self.result_table.clear()

            # Set column headers
            self.result_table.setColumnCount(6)
            self.result_table.setHorizontalHeaderLabels(["Name", "Website", "Phone", "Emails", "Street Address", "Status"])

            # Enable sorting for columns
            self.result_table.setSortingEnabled(True)

            for index, business in enumerate(businesses, start=1):
                place_details = self.get_place_details(business['place_id'])

                # Use .get() to handle missing values
                website = place_details.get('website', 'Website not available')
                phone = place_details.get('formatted_phone_number', 'Phone number not available')
                street_address = place_details.get('formatted_address', 'Address not available')

                # Set the initial status as "Not Contacted"
                initial_status = "Not Contacted"

                # Display data in separate columns
                row_position = self.result_table.rowCount()
                self.result_table.insertRow(row_position)
                self.result_table.setItem(row_position, 0, QTableWidgetItem(business['name']))
                self.result_table.setItem(row_position, 1, QTableWidgetItem(website))
                self.result_table.setItem(row_position, 2, QTableWidgetItem(phone))
                self.result_table.setItem(row_position, 3, QTableWidgetItem(', '.join(self.find_email_on_website(website))))
                self.result_table.setItem(row_position, 4, QTableWidgetItem(street_address))

                # Create a combo box for the status
                status_combobox = QComboBox()
                status_combobox.addItems(["Not Contacted", "Contacted", "Signed-up", "Declined Services"])
                status_combobox.setCurrentText(initial_status)  # Set the initial status
                self.result_table.setCellWidget(row_position, 5, status_combobox)

                # Connect the combobox signal to a slot
                status_combobox.currentIndexChanged.connect(lambda _, row=row_position: self.status_changed(row))

                # Set background color based on status
                status = status_combobox.currentText()
                self.set_status_background_color(row_position, status)

                # Auto-adjust column width based on content length
                self.result_table.resizeColumnsToContents()

                # Save results for later use
                saved_result = {
                    "Name": business['name'],
                    "Website": website,
                    "Phone": phone,
                    "Emails": ', '.join(self.find_email_on_website(website)),
                    "Street Address": street_address,
                    "Status": initial_status
                }
                self.saved_results.append(saved_result)

            # Save results to a file
            self.save_results()

        except Exception as e:
            print(f"Error: {e}")

    def status_changed(self, row):
        # Handle the status change event
        status_combobox = self.result_table.cellWidget(row, 5)
        status = status_combobox.currentText()
        self.set_status_background_color(row, status)

    def search_nearby_businesses(self, location, radius, business_type):
        places_url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={location[0]},{location[1]}&radius={radius}&type={business_type}&key={self.api_key}'
        response = requests.get(places_url)
        data = response.json()

        if data['status'] == 'OK':
            return data['results']
        else:
            raise Exception(f"Failed to fetch nearby businesses. Error: {data.get('error_message')}")

    def save_to_text_file(self, name, address, website, phone, emails, street_address, status):
        with open('businesses.txt', 'a') as file:
            file.write(f"Name: {name}\n")
            file.write(f"Address: {address}\n")
            file.write(f"Website: {website}\n")
            file.write(f"Phone: {phone}\n")
            file.write(f"Emails: {', '.join(emails)}\n")
            file.write(f"Street Address: {street_address}\n")
            file.write(f"Status: {status}\n\n")

    def set_status_background_color(self, row, status):
        color_dict = {
            "Not Contacted": QColor(255, 255, 255),  # White
            "Contacted": QColor(173, 216, 230),  # Light Blue
            "Signed-up": QColor(144, 238, 144),  # Light Green
            "Declined Services": QColor(255, 99, 71)  # Tomato Red
        }
        background_color = color_dict.get(status, QColor(255, 255, 255))  # Default to White
        for col in range(self.result_table.columnCount()):
            item = self.result_table.item(row, col)
            if item is not None:
                item.setBackground(background_color)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = BusinessFinderApp()
    window.show()
    sys.exit(app.exec_())
