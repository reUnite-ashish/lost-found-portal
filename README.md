# ReUnite - Lost & Found Portal 🔍

A modern, responsive web application to help people reunite with lost items and connect them with finders. Built with Flask, HTML, CSS, and JavaScript.

## Features ✨

- 🔐 **Secure User Authentication** - Protected accounts with encrypted passwords
- 📦 **Easy Item Reporting** - Report lost or found items with images
- 🔍 **Smart Search & Filter** - Find items by name, category, location
- 🗂️ **Category System** - Organized items (Mobile, Purse, ID Card, Documents, etc.)
- 🖼️ **Image Upload** - Upload and preview item images
- 🔄 **Automated Matching** - System auto-matches lost and found items
- 🔔 **Notifications** - Get alerts when matching items are found
- 🛡️ **Claim Verification** - Admin verification protects against fraud
- 👨‍💻 **Admin Panel** - Manage items, verify claims, monitor reports
- 🌐 **Responsive Design** - Works on desktop, tablet, and mobile
- ⚡ **Real-Time Updates** - Dynamic data without page reload

## Project Structure 📁

```
OPL/
├── app.py                 # Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── static/
│   ├── style.css         # CSS styling
│   ├── script.js         # JavaScript functionality
│   └── uploads/          # User uploaded images
└── templates/
    ├── index.html        # Home page
    ├── register.html     # User registration
    ├── login.html        # User login
    ├── browse.html       # Browse items
    ├── report.html       # Report new item
    ├── item_detail.html  # Item details page
    ├── claim.html        # Claim item page
    ├── admin_dashboard.html  # Admin panel
    ├── 404.html          # 404 error page
    └── 500.html          # 500 error page
```

## Installation & Setup 🚀

### Prerequisites
- Python 3.7+
- pip (Python package manager)

### Steps

1. **Clone/Download the project**
   ```bash
   cd c:\Users\amanb\OneDrive\Desktop\OPL
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   source venv/bin/activate # Mac/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   - Open your browser and go to `http://localhost:5000`

## Usage 📖

### For Users

1. **Register/Login** - Create an account or log in
2. **Report Item** - Click "Report an Item" to report lost/found items
3. **Browse Items** - Search and filter items by category, location, type
4. **Claim Item** - Submit proof of ownership to claim an item
5. **Wait for Verification** - Admin verifies your claim

### For Admins

1. **Access Admin Dashboard** - Go to `/admin` (must be admin user)
2. **View All Items** - See all reported items
3. **Review Claims** - Check pending claims with proof
4. **Verify/Reject** - Approve or reject claims

## Categories 🏷️

- 📱 Mobile Phone
- 👜 Wallet/Purse
- 🆔 ID Card/Documents
- 📄 Government Documents
- 💍 Jewelry
- 👕 Clothing
- 🔑 Keys
- 📦 Others

## Technologies Used 🛠️

- **Backend**: Python, Flask
- **Frontend**: HTML5, CSS3, JavaScript
- **Database**: In-memory (ready for MongoDB integration)
- **Styling**: Custom CSS with responsive design
- **File Upload**: Werkzeug

## How It Works 🔄

1. **User Reports an Item**
   - Provides item details, image, location
   - Item is stored in database

2. **System Matches Items**
   - Algorithm compares lost and found items
   - Matches based on category and description

3. **User Claims Item**
   - Submits proof of ownership
   - Admin verifies the claim

4. **Admin Verification**
   - Admin reviews claim
   - Approves or rejects based on proof

5. **Successful Recovery**
   - Item marked as claimed
   - Both parties contacted

## Security Features 🔒

- Password hashing with Werkzeug
- Session management
- Admin access control
- File upload validation
- Error handling

## Customization 🎨

### Change App Secret Key
Edit `app.py` line:
```python
app.secret_key = 'your-secret-key-change-this'
```

### Add MongoDB Integration
Replace in-memory database with MongoDB:
```python
from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017/')
db = client['reunite']
```

## Future Enhancements 🚀

- MongoDB integration for persistent storage
- Email notifications
- SMS alerts
- Location-based search (maps integration)
- Social media sharing
- ML-based image matching
- Mobile app
- Blockchain for verification

## Contributing 🤝

Feel free to fork, modify, and improve the project!

## License 📜

This project is open source and available under the MIT License.

## Support 📞

For issues or questions, please contact the development team.

## Windows Quick Run (Current Setup) 🪟

Use these commands from PowerShell in the project folder:

1. Install dependencies
   ```powershell
   C:/Users/amanb/AppData/Local/Programs/Python/Python314/python.exe -m pip install -r requirements.txt
   ```

2. (Optional) Set email credentials for notifications
   ```powershell
   $env:MAIL_USERNAME="your_gmail@gmail.com"
   $env:MAIL_PASSWORD="your_gmail_app_password"
   ```

3. Start app
   ```powershell
   C:/Users/amanb/AppData/Local/Programs/Python/Python314/python.exe app.py
   ```

4. Open in browser
   - http://127.0.0.1:5000

### Admin Health Checks

While logged in as admin, open:

- `/admin/health` → database and collection health
- `/admin/health/routes` → required admin route registration status

---

**Built with ❤️ for reuniting people with what matters**
