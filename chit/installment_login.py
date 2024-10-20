from django.http import Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import *
from .serializers import *
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from decimal import Decimal
from django.contrib.auth import update_session_auth_hash
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken



class UserInstallmentView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self,request):
        user = User.objects.select_related('chit_plan').get(id=request.user.id)
        payment_details = InstallmentSerializer(user).data
        return Response(payment_details, status=status.HTTP_200_OK)
        

    def post(self, request):
        user = User.objects.select_related('chit_plan').get(id=request.user.id)
        chit_plan = user.chit_plan
        
        if user.total_pending_amount == user.total_amount_paid:
            return Response({"message":"Your Already Completed The Chit Plan Claim Your Gold",
                             "Amount Paid":user.total_amount_paid,
                             "Bonus Amount":user.chit_plan.interest_amount,
                             "Final Amount":user.total_amount_paid+user.chit_plan.interest_amount
                             })
        
        
        if not chit_plan:
            return Response({"error": "No chit plan assigned."}, status=status.HTTP_400_BAD_REQUEST)

        installment_amount = chit_plan.plan
        payment = Decimal(request.data.get('payment', 0))  # Convert payment to Decimal

        
        # last_payment = Payment.objects.filter(user=user, chit_plan=chit_plan).order_by('-date_paid').first()
        # if last_payment and last_payment.date_paid.month == timezone.now().month:
        #     return Response({"error": "You have already made a payment for this month."},
        #                     status=status.HTTP_400_BAD_REQUEST)
  
        if installment_amount > payment:
            # print(installment_amount)
            # print(payment)
            return Response({"error":f"payment is not less then {installment_amount}"})  
        # Prevent overpayment

            
                     
        if user.missed_months == 0 and payment >= chit_plan.plan:
   
            # Calculate total due amount (missed months + pending amount)
            last_payment = Payment.objects.filter(user=user, chit_plan=chit_plan).order_by('-date_paid').first()
            if last_payment and last_payment.date_paid.month == timezone.now().month:
                return Response({"error": "You have already made a payment for this month."},
                            status=status.HTTP_400_BAD_REQUEST)

            remaining_payment = user.total_pending_amount - payment

        
            # Calculate total due amount (missed months + pending amount) 
        else:
            total_due = user.missed_months * installment_amount
            remaining_payment = user.total_pending_amount - total_due  
            user.missed_months = 0
        
        if payment > remaining_payment:
            return Response({"error": f"Overpayment not allowed. Your remaining balance is {remaining_payment}."},
                            status=status.HTTP_400_BAD_REQUEST)  

        # If payment covers all missed months and pending amounts
        month_no = payment // installment_amount

        if remaining_payment == 0:
            user.months_paid += user.missed_months
            user.missed_months -= month_no
            user.pending_amount = 0
        # If payment covers more than one month or partial payment
        elif payment >= installment_amount:
            months_covered = payment // installment_amount
            user.months_paid += int(months_covered)
            # user.pending_amount = payment % installment_amount
        # else:
        #     user.pending_amount -= payment

        # Update total amounts
        user.total_amount_paid += payment
        print(user.total_amount_paid)
        
        
        Payment.objects.create(
    user=user,
    chit_plan=chit_plan,
    installment_number=user.months_paid,  # Update based on logic
    amount_paid=user.total_amount_paid,  # Store the total amount paid so far
    status='Paid',
    last_payment_date=timezone.now(),
    last_payment_amount=payment # Store the current payment amount
)


        user.save()

        return Response({"message": "Installment payment processed successfully."}, status=status.HTTP_200_OK)
