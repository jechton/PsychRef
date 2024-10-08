import logging
import os
from collections import defaultdict
from datetime import datetime

import pandas as pd
from fpdf import FPDF

from constants import APP_EXPECTED_COLUMNS, DEM_EXPECTED_COLUMNS, REF_EXPECTED_COLUMNS
from utils import (
    check_file_columns,
    load_csv,
    parse_args,
    setup_logger,
)

global_gui_mode = False
PROCESSED_CLIENTS_FILE = "SentClientList.txt"
LOGO_FILE = "Logo.jpg"


def read_cache():
    if os.path.exists(PROCESSED_CLIENTS_FILE):
        with open(PROCESSED_CLIENTS_FILE, "r") as f:
            return set(f.read().split())
    return set()


def write_cache(processed_clients):
    with open(PROCESSED_CLIENTS_FILE, "w") as f:
        f.write(" ".join(str(client_id) for client_id in processed_clients))


def check_logo_file():
    if not os.path.exists(LOGO_FILE):
        error_message = f"Logo file '{LOGO_FILE}' not found. Please ensure the logo file is in the correct location."
        logging.error(error_message)
        raise FileNotFoundError(error_message)


def get_clients(dem_sheet, ref_sheet, app_sheet, code):
    logging.info(f"Fetching clients with code: {code}")
    app_sheet["STARTTIME"] = pd.to_datetime(app_sheet["STARTTIME"], errors="coerce")
    future_appointments = app_sheet[app_sheet["STARTTIME"] > datetime.now()]
    target_appointments = future_appointments[
        future_appointments["NAME"].str.contains(code, na=False)
    ]

    results = []

    for _, appointment in target_appointments.iterrows():
        client_id = appointment["CLIENT_ID"]
        logging.debug(f"Processing client ID: {client_id}")

        client_info = dem_sheet[dem_sheet["CLIENT_ID"] == client_id].iloc[0]

        first_name = client_info["FIRSTNAME"]
        preferred_name = client_info.get("PREFERRED_NAME", "")
        if pd.notna(preferred_name) and preferred_name.lower() != first_name.lower():
            first_name += f' "{preferred_name}"'

        client_name_for_lookup = f"{client_info['FIRSTNAME']} {client_info['LASTNAME']}"
        client_name = f"{first_name} {client_info['LASTNAME']}"

        referral_info = ref_sheet[ref_sheet["Client Name"] == client_name_for_lookup]

        if referral_info.empty and pd.notna(preferred_name):
            preferred_name_lookup = f"{preferred_name} {client_info['LASTNAME']}"
            referral_info = ref_sheet[ref_sheet["Client Name"] == preferred_name_lookup]

        referral_source = (
            referral_info["Referral Name"].iloc[0]
            if not referral_info.empty
            else "Unknown"
        )

        appointment_time = (
            "Unknown Time"
            if pd.isna(appointment["STARTTIME"])
            else appointment["STARTTIME"].strftime("%m/%d/%Y %I:%M %p")
        )

        results.append(
            {
                "client_id": client_id,
                "client_name": client_name,
                "appointment_time": appointment_time,
                "referral_source": referral_source,
            }
        )

    logging.info(f"Found {len(results)} clients with code {code}")
    return results


def create_referral_pdfs(clients):
    logging.info("Creating referral PDFs")
    referral_groups = defaultdict(list)
    for client in clients:
        if client["referral_source"].lower() not in [
            "unknown",
            "no referral source",
            "",
            "babynet",
        ]:
            referral_groups[client["referral_source"]].append(client)

    for referral_source, clients in referral_groups.items():
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Times", size=12)
        pdf.image("Logo.jpg", w=100, x=50)

        referral_name = referral_source.split("(")[0].strip().title()

        pdf.ln(5)
        pdf.multi_cell(0, 10, f"Hi {referral_name},")
        pdf.ln(1)
        pdf.multi_cell(
            0,
            10,
            "Thank you for referring the following clients. Here is a list of their tentative evaluation appointments:",
        )
        pdf.ln(5)

        # Write client appointments
        for client in clients:
            if client["appointment_time"] != "Unknown Time":
                # Parse the datetime
                appointment_datetime = datetime.strptime(
                    client["appointment_time"], "%m/%d/%Y %I:%M %p"
                )
                # Format the appointment string
                appointment_str = (
                    f"{client['client_name']} on "
                    f"{appointment_datetime.strftime('%m/%d/%Y')} at "
                    f"{appointment_datetime.strftime('%-I:%M %p')}"
                )
            else:
                appointment_str = f"{client['client_name']} - Appointment time unknown"

            pdf.multi_cell(0, 10, appointment_str)

        pdf.ln(5)
        pdf.multi_cell(0, 10, "Thank you again!")
        pdf.multi_cell(0, 10, "Driftwood Evaluation Center")

        footer_text = "Confidentiality Statement. The documents accompanying this transmission contain confidential health information that is legally protected. This information is intended only for the use of the individuals or entities listed above. If you are not the intended recipient, you are hereby notified that any disclosure, copying, distribution, or action taken in reliance on the contents of these documents is strictly prohibited if you have received this information in error, please notify the sender immediately and arrange for the return or destruction of these documents."

        pdf.set_y(-42)  # Move to 30mm from bottom
        pdf.set_font("Times", "I", 8)
        pdf.multi_cell(0, 5, footer_text)

        safe_filename = referral_name.rstrip()
        pdf_filename = f"PDFs/{safe_filename}.pdf"

        # Check if the file already exists
        counter = 1
        while os.path.exists(pdf_filename):
            pdf_filename = f"PDFs/{safe_filename}_{counter}.pdf"
            counter += 1

        pdf.output(pdf_filename)
        logging.info(f"Created PDF: {pdf_filename}")


def process_data(dem_sheet, ref_sheet, app_sheet):
    logging.info("Starting data processing")

    try:
        check_logo_file()
    except FileNotFoundError as e:
        logging.error(str(e))
        return  # Exit the function if logo is not found

    os.makedirs("PDFs/", exist_ok=True)
    if dem_sheet is not None and ref_sheet is not None and app_sheet is not None:
        processed_clients = read_cache()
        clients_96136 = get_clients(dem_sheet, ref_sheet, app_sheet, "96136")

        new_clients = [
            client
            for client in clients_96136
            if str(client["client_id"]) not in processed_clients
        ]

        if new_clients:
            create_referral_pdfs(new_clients)

            # Update the cache with new client IDs (as strings)
            processed_clients.update(str(client["client_id"]) for client in new_clients)
            write_cache(processed_clients)

            logging.info(
                f"Found {len(new_clients)} new clients with '96136' appointments."
            )
        else:
            logging.info("No new clients found.")
    else:
        logging.error("One or more required sheets are missing.")


def main():
    args = parse_args()
    global global_gui_mode
    if args.dem and args.ref and args.app:
        setup_logger(gui_mode=False)
        logging.info("Starting in command-line mode.")
        dem_sheet = load_csv(args.dem)
        ref_sheet = load_csv(args.ref)
        app_sheet = load_csv(args.app)

        if (
            check_file_columns(dem_sheet, DEM_EXPECTED_COLUMNS, "Demographics")
            and check_file_columns(ref_sheet, REF_EXPECTED_COLUMNS, "Referral")
            and check_file_columns(app_sheet, APP_EXPECTED_COLUMNS, "Appointments")
        ):
            process_data(dem_sheet, ref_sheet, app_sheet)

    else:
        global_gui_mode = True
        logging.info("Starting in GUI mode.")
        from gui import App

        app = App()
        app.mainloop()


if __name__ == "__main__":
    main()
