from datetime import datetime
from dateutil.relativedelta import relativedelta

# Assuming last_paid_date is a datetime object
last_paid_date = datetime.now()  # Example: current date
next_month_date = last_paid_date + relativedelta(months=1)

print("Next Payment Date:", next_month_date)
