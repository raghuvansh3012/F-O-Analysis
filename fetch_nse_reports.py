
import requests
import datetime
import os
import sys

# paths set kar lo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# default date aaj ki rahegi, ya user argument me bhej sakta hai
# dhyaan rahe aaj ka data shaam 5:30 ke baad hi aata hai nse website pe

def get_target_date():
    if len(sys.argv) > 1:
        try:
            return datetime.datetime.strptime(sys.argv[1], "%d-%m-%Y").date()
        except ValueError:
            print("Invalid date format. Please use DD-MM-YYYY.")
            sys.exit(1)
    return datetime.date.today()

def download_file(url, save_path):
    print(f"Attempting to download: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=15)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Successfully saved to: {save_path}")
            return True
        else:
            print(f"Failed to download. Status Code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def main():
    target_date = get_target_date()
    # dates format set kar lo
    dd = target_date.strftime("%d")
    mm = target_date.strftime("%m")
    yyyy = target_date.strftime("%Y")
    
    # file ke naam fix kar lete hain
    date_str = f"{dd}{mm}{yyyy}"
    
    # in reports ke URL set karte hain
    # nse ki website pe url change hote rehte hain, but mostly yehi paths chalte hain
    
    reports = [
        {
            "name": "Participant Open Interest",
            "filename": f"fao_participant_oi_{date_str}.csv",
            "urls": [
                f"https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{date_str}.csv",
                f"https://www.nseindia.com/content/nsccl/fao_participant_oi_{date_str}.csv" 
            ]
        },
        {
            "name": "Participant Volume",
            "filename": f"fao_participant_vol_{date_str}.csv",
            "urls": [
                f"https://nsearchives.nseindia.com/content/nsccl/fao_participant_vol_{date_str}.csv",
                 f"https://www.nseindia.com/content/nsccl/fao_participant_vol_{date_str}.csv"
            ]
        },
    ]

    reports.append({
        "name": "Index Closing Data",
        "filename": f"ind_close_all_{date_str}.csv",
        "urls": [
             f"https://archives.nseindia.com/content/indices/ind_close_all_{date_str}.csv",
             f"https://www.nseindia.com/content/indices/ind_close_all_{date_str}.csv"
        ]
    })


    print(f"Fetching F&O Reports for Date: {target_date.strftime('%d-%m-%Y')}")
    print("-" * 50)

    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)

    for report in reports:
        success = False
        save_path = os.path.join(BASE_DIR, report['filename'])
        
        for url in report['urls']:
            if download_file(url, save_path):
                success = True
                break
        
        if not success:
            print(f"Wait... unable to fetch {report['name']} from known URLs.")
            # TODO: agar aaj data na mile toh pichle din ka check karne ka logic add karna hai baad me
            # abhi ke liye bas fail dikha do

if __name__ == "__main__":
    main()
