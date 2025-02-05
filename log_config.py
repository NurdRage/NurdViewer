import os

def get_central_logging_ip():
    """
    Check for the CENTRAL_LOG_IP environment variable.
    If not set, prompt the user if they want to enable centralized logging.
    If the user declines (or enters no value), return None.
    Otherwise, return the IP address entered (or the existing environment value).
    """
    ip = os.environ.get("CENTRAL_LOG_IP")
    if ip:
        return ip.strip()
    else:
        try:
            # Ask the user if they want to set up centralized logging
            response = input("CENTRAL_LOG_IP is not set. Would you like to configure centralized logging? (y/n): ")
            if response.lower().startswith("y"):
                ip_input = input("Please enter the central logging server IP (default is 127.0.0.1): ")
                ip_final = ip_input.strip() if ip_input.strip() else "127.0.0.1"
                os.environ["CENTRAL_LOG_IP"] = ip_final
                return ip_final
            else:
                # User declined centralized logging
                return None
        except Exception as e:
            print(f"Error during centralized logging configuration: {e}")
            return None

