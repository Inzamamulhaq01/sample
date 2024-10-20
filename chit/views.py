from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import *
from .serializers import *
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from django.contrib.auth import update_session_auth_hash
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken



class ChangePasswordView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    

    def post(self, request):
        user = request.user
        serializer = PasswordChangeSerializer(data=request.data)
        
        if serializer.is_valid():
            # Set the new password
            pass1 = serializer.validated_data['password']
            pass2 = serializer.validated_data['conf_password']
            if pass1 != pass2:
                return Response({"error":"password does not match!"})
            user.set_password(serializer.validated_data['password'])
            # user.needs_password_change = False  # Mark that password has been changed
            user.save()

            # Keep the user logged in after password change
            update_session_auth_hash(request, user)
            
            return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)







class UserInstallmentView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = User.objects.select_related('chit_plan').get(id=request.user.id)
        payment_details = InstallmentSerializer(user).data
        return Response(payment_details, status=status.HTTP_200_OK)

    def post(self, request):
        user = User.objects.select_related('chit_plan').get(id=request.user.id)
        chit_plan = user.chit_plan

        # Check if the user has completed the chit plan
        if user.total_pending_amount == user.total_amount_paid:
            return Response({
                "message": "You have already completed the Chit Plan. Claim your gold.",
                "Amount Paid": user.total_amount_paid,
                "Bonus Amount": user.chit_plan.interest_amount,
                "Final Amount": user.total_amount_paid + user.chit_plan.interest_amount
            })

        if not chit_plan:
            return Response({"error": "No chit plan assigned."}, status=status.HTTP_400_BAD_REQUEST)

        installment_amount = chit_plan.plan
        payment = Decimal(request.data.get('payment', 0))  # Convert payment to Decimal

        # Validate payment amount
        if payment <= 0:
            return Response({"error": "Payment amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        if payment < installment_amount:
            return Response({"error": f"Payment must be at least {installment_amount}."}, status=status.HTTP_400_BAD_REQUEST)

        # last_payment = Payment.objects.filter(user=user, chit_plan=chit_plan).order_by('-date_paid').first()
        # if last_payment and last_payment.date_paid.month == timezone.now().month:
        #     return Response({"error": "You have already made a payment for this month."},
        #                     status=status.HTTP_400_BAD_REQUEST)

        # Calculate total due amount (for missed months)
        missed_months = user.missed_months

        # Process missed payments first
        if missed_months > 0:
            total_due_for_missed = missed_months * installment_amount
            
            if payment >= total_due_for_missed:
                # Pay off all missed months
                user.total_amount_paid += total_due_for_missed
                user.months_paid += missed_months
                user.missed_months = 0  # Reset missed months
                payment -= total_due_for_missed  # Reduce payment by the amount used for missed months
            else:
                # Pay only part of the missed months
                months_paid_with_payment = payment // installment_amount
                user.missed_months -= months_paid_with_payment  # Reduce missed months based on payment
                user.total_amount_paid += months_paid_with_payment * installment_amount  # Update total paid
                user.months_paid += months_paid_with_payment  # Update months paid
                payment = 0  # All payment has been accounted for
        else:
            # No missed months, just process the current installment payment
            if payment >= installment_amount:
                months_to_pay = payment // installment_amount
                user.months_paid += months_to_pay
                user.total_amount_paid += months_to_pay * installment_amount
                payment %= installment_amount  # Remaining amount after full months paid

        # Check if this will create a duplicate installment entry

        Payment.objects.create(
                user=user,
                chit_plan=chit_plan,
                installment_number=user.months_paid,  # Current month installment
                amount_paid=user.total_amount_paid,  # Store the total amount paid so far
                status='Paid',
                last_payment_date=timezone.now(),
                last_payment_amount=payment
            )


        # Save the user object
        user.save()

        return Response({"message": "Installment payment processed successfully."}, status=status.HTTP_200_OK)


class UserView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = User.objects.select_related('chit_plan').get(id=request.user.id)
        # Apply select_related to optimize chit_plan retrieval
        if user.total_pending_amount == user.total_amount_paid:
            return Response({"message":"Your Already Completed The Chit Plan Claim Your Gold",
                        "Amount Paid":user.total_amount_paid,
                        "Bonus Amount":user.chit_plan.interest_amount,
                        "Final Amount":user.total_amount_paid+user.chit_plan.interest_amount
                        })
        
        user = User.objects.select_related('chit_plan').get(id=request.user.id)
        user_serializer = UserSerializer(user).data
        return Response(user_serializer, status=status.HTTP_200_OK)



class LoginView(APIView):
    authentication_classes = []  # Disable authentication
    permission_classes = [] 
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"status": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data.get('username')
        password = serializer.validated_data.get('password')

        user_obj = authenticate(username=username, password=password)
        if user_obj:
            token = RefreshToken.for_user(user_obj)
            return Response({
                "status":200,
                "message": "Login successful", 
                "username": username, 
                "access_token": str(token.access_token),
                "refresh_token": str(token)
                
                })
        return Response({"error": "Invalid username or password","status":400}, status=status.HTTP_401_UNAUTHORIZED)
    
    def get(self,request):
        return Response({"Success"})


# class PaymentPagination(PageNumberPagination):
#     page_size = 10


# class UserPaymentList(APIView):
#     authentication_classes = [SessionAuthentication, TokenAuthentication]
#     permission_classes = [IsAuthenticated]
#     pagination_class = PaymentPagination

#     def get(self, request):
#         payments = Payment.objects.filter(user=request.user).order_by('installment_number')
#         paginator = PaymentPagination()
#         result_page = paginator.paginate_queryset(payments, request)
#         serializer = PaymentSerializer(result_page, many=True)
#         return paginator.get_paginated_response(serializer.data)

