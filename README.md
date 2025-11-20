# Cars-Recall
<img width="1078" height="868" alt="image" src="https://github.com/user-attachments/assets/28c8c67b-3005-428e-b2d8-4a6658dafd29" />


# 🚗 Israel Vehicle Recall Checker (2025)

A lightweight, client-side web application that allows users to check if their vehicle has an open recall notice ("kriat sherut") in Israel. The system provides an instant status check and visualizes national safety statistics.

> **📅 Data Validity:** This project relies on the Ministry of Transport dataset updated as of **November 20, 2025**.

## 📋 Features

*   **Instant Search:** Enter a 7 or 8-digit license plate number to check for open recalls.
*   **Detailed Reports:** If a recall is found, the app displays the fault description, repair method, and importer contact details.
*   **Analytics Dashboard:**
    *   **Timeline:** Recall trends by manufacturer (2000-2025) using distinct, matte colors.
    *   **Status:** Breakdown of open vs. closed recalls.
    *   **Fault Analysis:** Distribution of technical issues (Airbags, Brakes, Engine, etc.).
    *   **High Risk Models:** Top 10 car models with the most open recalls.
*   **Responsive Design:** Fully optimized for mobile and desktop using Tailwind CSS.

## 🛠️ Tech Stack

*   **HTML5 / CSS3**
*   **Tailwind CSS** (Styling via CDN)
*   **JavaScript (ES6+)**
*   **Chart.js** (Data visualization with custom pastel palettes)


## 📂 Data Structure & Optimization

This project is designed to run entirely in the browser without a backend database.

1.  **Source:** Israel Ministry of Transport open data.
2.  **Optimization:** To ensure fast search performance on the client side, the massive dataset is split into smaller CSV files (`data_0.csv` through `data_9.csv`) located in the `split_data/` folder.
3.  **Logic:** The script reads the last digit of the user's input (license plate) and fetches only the relevant CSV file to minimize bandwidth and processing time.


## ⚠️ Disclaimer
This tool is for informational purposes only. The data is a snapshot correct as of **20/11/2025**. For the most current and legally binding information, please consult the official Israeli Ministry of Transport website or contact the vehicle importer directly.

---

**Created:** November 2025

This tool is for informational purposes only. The data is a snapshot correct as of **20/11/2025**. For the most current and legally binding information, please consult the official Israeli Ministry of Transport website or contact the vehicle importer directly.

---

**Created:** November 2025
