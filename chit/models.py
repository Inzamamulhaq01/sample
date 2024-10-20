from django.db import models
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.models import AbstractUser


class UserActionLog(models.Model):
    ACTION_CHOICES = [
        ('CREATED', 'Created'),
        ('DELETED', 'Deleted'),
    ]
    user_name = models.CharField(max_length=50)
    user = models.ForeignKey('User', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.action} | User: {self.user_name} | Timestamp: {self.timestamp}'


class ChitPlan(models.Model):
    PLAN_CHOICES = [
        (500, '500'),
        (1000, '1000'),
    ]
    plan = models.IntegerField(choices=PLAN_CHOICES, default=500)
    interest_amount = models.DecimalField(max_digits=10, decimal_places=2, default=750)
    duration = models.PositiveIntegerField(default=11)
    amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0)

    def save(self, *args, **kwargs):
        self.amount = self.plan * self.duration
        self.total_amount = self.amount + self.interest_amount
        super(ChitPlan, self).save(*args, **kwargs)

    def __str__(self):
        return f"Plan {self.plan}"

class User(AbstractUser):
    phone_number = models.CharField(max_length=20)
    chit_plan = models.ForeignKey(ChitPlan, on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    months_paid = models.PositiveIntegerField(default=0)
    missed_months = models.PositiveIntegerField(default=0)
    pending_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_pending_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    account_created_date = models.DateField(default=timezone.now)

    def calculate_missed_months(self):
        """Calculate the number of months missed based on account creation date."""
        current_date = timezone.now().date()
        account_creation_months = (current_date.year - self.account_created_date.year) * 12 + (current_date.month - self.account_created_date.month)
        
        # Calculate missed months
        missed_months = max(account_creation_months - self.months_paid, 0)
        self.missed_months = missed_months

        if self.chit_plan:
            self.pending_amount = self.missed_months * self.chit_plan.plan
            self.total_pending_amount = self.pending_amount
        
        return self.missed_months

    def update_pending_amount(self):
        """Update pending amount based on missed months."""
        self.calculate_missed_months()
        self.save()

    def make_payment(self, amount):
        """Process payment and update months paid."""
        chit_plan_value = self.chit_plan.plan if self.chit_plan else Decimal(0)

        if amount >= self.pending_amount:
            # Full payment for missed months
            self.total_amount_paid += amount
            self.months_paid += self.missed_months
            self.missed_months = 0
            self.pending_amount = 0
        else:
            # Partial payment
            self.total_amount_paid += amount
            
            # Calculate how many full installments can be paid
            installments_covered = int(amount // chit_plan_value)
            if installments_covered > 0:
                self.months_paid += installments_covered
                self.missed_months -= installments_covered
            
            # Update pending amount after the partial payment
            self.pending_amount = self.missed_months * chit_plan_value

        self.save()

    def calculate_final_payout(self):
        """Calculate final payout after completing the plan."""
        if self.months_paid == self.chit_plan.duration:
            return self.total_amount_paid + self.chit_plan.interest_amount
        return 0




@receiver(post_save, sender=User)
def log_user_creation(sender, instance, created, **kwargs):
    if created:
        # Assuming the initial current month is 0 when the user is created
        initial_current_month = 0  
        instance.update_pending_amount(initial_current_month)  # Pass the initial value
        UserActionLog.objects.create(
            user_name=instance.username,
            user=instance, 
            action='CREATED'
        )


@receiver(pre_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    UserActionLog.objects.create(
        user_name=instance.username,
        user=instance, 
        action='DELETED', 
        timestamp=timezone.now()
    )


from django.utils import timezone
from django.db import models

class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    chit_plan = models.ForeignKey(ChitPlan, on_delete=models.CASCADE, related_name='payments')
    installment_number = models.PositiveIntegerField()
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    date_paid = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, default='Paid')
    last_payment_date = models.DateTimeField(null=True, blank=True)
    last_payment_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'User: {self.user.username} | Installment: {self.installment_number} | Amount: {self.amount_paid} | Status: {self.status}'

    def save(self, *args, **kwargs):
        # Automatically update last payment fields when saving a payment
        self.last_payment_date = timezone.now()
        super(Payment, self).save(*args, **kwargs)
