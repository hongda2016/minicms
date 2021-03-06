import datetime
import hashlib
import re

from datetime import timedelta

from django.utils import six
from django.apps import apps
from django.conf import settings
from django.core import mail
from django.core import management
from django.test import override_settings
from django.test import TestCase
from django.utils.timezone import now as datetime_now

from registration.models import RegistrationProfile, SupervisedRegistrationProfile
from registration.users import UserModel

Site = apps.get_model('sites', 'Site')


class RegistrationModelTests(TestCase):
    """
    Test the model and manager used in the default backend.

    """
    user_info = {'username': 'alice',
                 'password': 'swordfish',
                 'email': 'alice@example.com'}

    registration_profile = RegistrationProfile

    def setUp(self):
        self.old_activation = getattr(settings,
                                      'ACCOUNT_ACTIVATION_DAYS', None)
        self.old_reg_email = getattr(settings,
                                     'REGISTRATION_DEFAULT_FROM_EMAIL', None)
        self.old_email_html = getattr(settings,
                                      'REGISTRATION_EMAIL_HTML', None)
        self.old_django_email = getattr(settings,
                                        'DEFAULT_FROM_EMAIL', None)

        settings.ACCOUNT_ACTIVATION_DAYS = 7
        settings.REGISTRATION_DEFAULT_FROM_EMAIL = 'registration@email.com'
        settings.REGISTRATION_EMAIL_HTML = True
        settings.DEFAULT_FROM_EMAIL = 'django@email.com'

    def tearDown(self):
        settings.ACCOUNT_ACTIVATION_DAYS = self.old_activation
        settings.REGISTRATION_DEFAULT_FROM_EMAIL = self.old_reg_email
        settings.REGISTRATION_EMAIL_HTML = self.old_email_html
        settings.DEFAULT_FROM_EMAIL = self.old_django_email

    def test_profile_creation(self):
        """
        Creating a registration profile for a user populates the
        profile with the correct user and a SHA1 hash to use as
        activation key.

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)

        self.assertEqual(self.registration_profile.objects.count(), 1)
        self.assertEqual(profile.user.id, new_user.id)
        self.failUnless(re.match('^[a-f0-9]{40}$', profile.activation_key))
        self.assertEqual(six.text_type(profile),
                         "Registration information for alice")

    def test_activation_email(self):
        """
        ``RegistrationProfile.send_activation_email`` sends an
        email.

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_activation_email(Site.objects.get_current())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user_info['email']])

    @override_settings(ACTIVATION_EMAIL_HTML='does-not-exist')
    def test_activation_email_missing_template(self):
        """
        ``RegistrationProfile.send_activation_email`` sends an
        email.

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_activation_email(Site.objects.get_current())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user_info['email']])

    def test_activation_email_uses_registration_default_from_email(self):
        """
        ``RegistrationProfile.send_activation_email`` sends an
        email.

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_activation_email(Site.objects.get_current())
        self.assertEqual(mail.outbox[0].from_email, 'registration@email.com')

    def test_activation_email_falls_back_to_django_default_from_email(self):
        """
        ``RegistrationProfile.send_activation_email`` sends an
        email.

        """
        settings.REGISTRATION_DEFAULT_FROM_EMAIL = None
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_activation_email(Site.objects.get_current())
        self.assertEqual(mail.outbox[0].from_email, 'django@email.com')

    def test_activation_email_is_html_by_default(self):
        """
        ``RegistrationProfile.send_activation_email`` sends an html
        email by default.

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_activation_email(Site.objects.get_current())

        self.assertEqual(len(mail.outbox[0].alternatives), 1)

    def test_activation_email_is_plain_text_if_html_disabled(self):
        """
        ``RegistrationProfile.send_activation_email`` sends a plain
        text email if settings.REGISTRATION_EMAIL_HTML is False.

        """
        settings.REGISTRATION_EMAIL_HTML = False
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_activation_email(Site.objects.get_current())

        self.assertEqual(len(mail.outbox[0].alternatives), 0)

    def test_user_creation(self):
        """
        Creating a new user populates the correct data, and sets the
        user's account inactive.

        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        self.assertEqual(new_user.username, 'alice')
        self.assertEqual(new_user.email, 'alice@example.com')
        self.failUnless(new_user.check_password('swordfish'))
        self.failIf(new_user.is_active)
        self.failIf(new_user.date_joined <=
                    datetime_now() - timedelta(
                        settings.ACCOUNT_ACTIVATION_DAYS)
                    )

    def test_user_creation_email(self):
        """
        By default, creating a new user sends an activation email.

        """
        self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        self.assertEqual(len(mail.outbox), 1)

    def test_user_creation_no_email(self):
        """
        Passing ``send_email=False`` when creating a new user will not
        send an activation email.

        """
        self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(),
            send_email=False, **self.user_info)
        self.assertEqual(len(mail.outbox), 0)

    def test_user_creation_old_date_joined(self):
        """
        If ``user.date_joined`` is well in the past, ensure that we reset it.
        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        self.assertEqual(new_user.username, 'alice')
        self.assertEqual(new_user.email, 'alice@example.com')
        self.failUnless(new_user.check_password('swordfish'))
        self.failIf(new_user.is_active)
        self.failIf(new_user.date_joined <=
                    datetime_now() - timedelta(
                        settings.ACCOUNT_ACTIVATION_DAYS)
                    )

    def test_unexpired_account_old_date_joined(self):
        """
        ``RegistrationProfile.activation_key_expired()`` is ``False`` within
        the activation window. Even if the user was created in the past.

        """
        self.user_info['date_joined'] = datetime_now(
        ) - timedelta(settings.ACCOUNT_ACTIVATION_DAYS + 1)
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        self.failIf(profile.activation_key_expired())

    def test_unexpired_account(self):
        """
        ``RegistrationProfile.activation_key_expired()`` is ``False``
        within the activation window.

        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        self.failIf(profile.activation_key_expired())

    def test_expired_account(self):
        """
        ``RegistrationProfile.activation_key_expired()`` is ``True``
        outside the activation window.

        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        new_user.date_joined -= datetime.timedelta(
            days=settings.ACCOUNT_ACTIVATION_DAYS + 1)
        new_user.save()
        profile = self.registration_profile.objects.get(user=new_user)
        self.failUnless(profile.activation_key_expired())

    def test_valid_activation(self):
        """
        Activating a user within the permitted window makes the
        account active, and resets the activation key.

        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        activated = (self.registration_profile.objects
                     .activate_user(profile.activation_key))

        self.failUnless(isinstance(activated, UserModel()))
        self.assertEqual(activated.id, new_user.id)
        self.failUnless(activated.is_active)

        profile = self.registration_profile.objects.get(user=new_user)
        self.assertTrue(profile.activated)

    def test_valid_activation_with_profile(self):
        """
        Activating a user within the permitted window makes the
        account active, and resets the activation key.

        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        activated_profile = (self.registration_profile.objects
                             .activate_user(profile.activation_key, get_profile=True))

        self.failUnless(isinstance(activated_profile, self.registration_profile))
        self.assertEqual(activated_profile.id, profile.id)
        self.failUnless(activated_profile.activated)

        new_user.refresh_from_db()
        self.assertTrue(activated_profile.user.id, new_user.id)
        self.assertTrue(new_user.is_active)

    def test_expired_activation(self):
        """
        Attempting to activate outside the permitted window does not
        activate the account.

        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        new_user.date_joined -= datetime.timedelta(
            days=settings.ACCOUNT_ACTIVATION_DAYS + 1)
        new_user.save()

        profile = self.registration_profile.objects.get(user=new_user)
        activated = (self.registration_profile.objects
                     .activate_user(profile.activation_key))

        self.failIf(isinstance(activated, UserModel()))
        self.failIf(activated)

        new_user = UserModel().objects.get(username='alice')
        self.failIf(new_user.is_active)

        profile = self.registration_profile.objects.get(user=new_user)
        self.assertFalse(profile.activated)

    def test_activation_invalid_key(self):
        """
        Attempting to activate with a key which is not a SHA1 hash
        fails.

        """
        self.failIf(self.registration_profile.objects.activate_user('foo'))

    def test_activation_already_activated(self):
        """
        Attempting to re-activate an already-activated account fails.

        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        self.registration_profile.objects.activate_user(profile.activation_key)

        profile = self.registration_profile.objects.get(user=new_user)
        self.assertEqual(self.registration_profile.objects.activate_user(
            profile.activation_key), new_user)

    def test_activation_deactivated(self):
        """
        Attempting to re-activate a deactivated account fails.
        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        self.registration_profile.objects.activate_user(profile.activation_key)

        # Deactivate the new user.
        new_user.is_active = False
        new_user.save()

        # Try to activate again and ensure False is returned.
        failed = self.registration_profile.objects.activate_user(
            profile.activation_key)
        self.assertFalse(failed)

    def test_activation_nonexistent_key(self):
        """
        Attempting to activate with a non-existent key (i.e., one not
        associated with any account) fails.

        """
        # Due to the way activation keys are constructed during
        # registration, this will never be a valid key.
        invalid_key = hashlib.sha1(six.b('foo')).hexdigest()
        self.failIf(self.registration_profile.objects.activate_user(invalid_key))

    def test_expired_user_deletion(self):
        """
        ``RegistrationProfile.objects.delete_expired_users()`` only
        deletes inactive users whose activation window has expired.

        """
        self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        expired_user = (self.registration_profile.objects
                        .create_inactive_user(
                            site=Site.objects.get_current(),
                            username='bob',
                            password='secret',
                            email='bob@example.com'))
        expired_user.date_joined -= datetime.timedelta(
            days=settings.ACCOUNT_ACTIVATION_DAYS + 1)
        expired_user.save()

        self.registration_profile.objects.delete_expired_users()
        self.assertEqual(self.registration_profile.objects.count(), 1)
        self.assertRaises(UserModel().DoesNotExist,
                          UserModel().objects.get, username='bob')

    def test_expired_user_deletion_missing_user(self):
        """
        ``RegistrationProfile.objects.delete_expired_users()`` only deletes
        inactive users whose activation window has expired. If a ``UserModel``
        is not present, the delete continues gracefully.

        """
        self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        expired_user = (self.registration_profile.objects
                        .create_inactive_user(
                            site=Site.objects.get_current(),
                            username='bob',
                            password='secret',
                            email='bob@example.com'))
        expired_user.date_joined -= datetime.timedelta(
            days=settings.ACCOUNT_ACTIVATION_DAYS + 1)
        expired_user.save()
        # Ensure that we cleanup the expired profile even if the user does not
        # exist
        expired_user.delete()

        self.registration_profile.objects.delete_expired_users()
        self.assertEqual(self.registration_profile.objects.count(), 1)
        self.assertRaises(UserModel().DoesNotExist,
                          UserModel().objects.get, username='bob')

    def test_management_command(self):
        """
        The ``cleanupregistration`` management command properly
        deletes expired accounts.

        """
        self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        expired_user = (self.registration_profile.objects
                        .create_inactive_user(site=Site.objects.get_current(),
                                              username='bob',
                                              password='secret',
                                              email='bob@example.com'))
        expired_user.date_joined -= datetime.timedelta(
            days=settings.ACCOUNT_ACTIVATION_DAYS + 1)
        expired_user.save()

        management.call_command('cleanupregistration')
        self.assertEqual(self.registration_profile.objects.count(), 1)
        self.assertRaises(UserModel().DoesNotExist,
                          UserModel().objects.get, username='bob')

    def test_resend_activation_email(self):
        """
        Test resending activation email to an existing user
        """
        user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), send_email=False, **self.user_info)
        self.assertEqual(len(mail.outbox), 0)

        profile = self.registration_profile.objects.get(user=user)
        orig_activation_key = profile.activation_key

        self.assertTrue(self.registration_profile.objects.resend_activation_mail(
            email=self.user_info['email'],
            site=Site.objects.get_current(),
        ))

        profile = self.registration_profile.objects.get(pk=profile.pk)
        new_activation_key = profile.activation_key

        self.assertNotEqual(orig_activation_key, new_activation_key)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_activation_email_nonexistent_user(self):
        """
        Test resending activation email to a nonexisting user
        """
        self.assertFalse(self.registration_profile.objects.resend_activation_mail(
            email=self.user_info['email'],
            site=Site.objects.get_current(),
        ))
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_activation_email_activated_user(self):
        """
        Test the scenario where user tries to resend activation code
        to the already activated user's email
        """
        user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), send_email=False, **self.user_info)

        profile = self.registration_profile.objects.get(user=user)
        activated = (self.registration_profile.objects
                     .activate_user(profile.activation_key))
        self.assertTrue(activated.is_active)

        self.assertFalse(self.registration_profile.objects.resend_activation_mail(
            email=self.user_info['email'],
            site=Site.objects.get_current(),
        ))
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_activation_email_expired_user(self):
        """
        Test the scenario where user tries to resend activation code
        to the expired user's email
        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), send_email=False, **self.user_info)
        new_user.date_joined -= datetime.timedelta(
            days=settings.ACCOUNT_ACTIVATION_DAYS + 1)
        new_user.save()

        profile = self.registration_profile.objects.get(user=new_user)
        self.assertTrue(profile.activation_key_expired())

        self.assertFalse(self.registration_profile.objects.resend_activation_mail(
            email=self.user_info['email'],
            site=Site.objects.get_current(),
        ))
        self.assertEqual(len(mail.outbox), 0)


@override_settings(
    ADMINS=(
        ('T-Rex', 'admin1@iamtrex.com'),
        ('Flea', 'admin2@iamaflea.com')
    )
)
class SupervisedRegistrationModelTests(RegistrationModelTests):
    """
    Test the model and manager used in the admin_approval backend.

    """

    user_info = {'username': 'alice',
                 'password': 'swordfish',
                 'email': 'alice@example.com'}

    registration_profile = SupervisedRegistrationProfile

    def test_valid_activation(self):
        """
        Activating a user within the permitted window makes the
        account active, and resets the activation key.

        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        activated = (self.registration_profile.objects
                     .activate_user(profile.activation_key))

        self.failUnless(isinstance(activated, UserModel()))
        self.assertEqual(activated.id, new_user.id)
        self.failIf(activated.is_active)

        profile = self.registration_profile.objects.get(user=new_user)
        self.assertTrue(profile.activated)

    def test_valid_activation_with_profile(self):
        """
        Activating a user within the permitted window makes the
        account active, and resets the activation key.

        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        activated_profile = (self.registration_profile.objects
                             .activate_user(profile.activation_key, get_profile=True))

        self.failUnless(isinstance(activated_profile, self.registration_profile))
        self.assertEqual(activated_profile.id, profile.id)
        self.failUnless(activated_profile.activated)

        new_user.refresh_from_db()
        self.assertTrue(activated_profile.user.id, new_user.id)
        self.assertFalse(new_user.is_active)

    def test_resend_activation_email_activated_user(self):
        """
        Test the scenario where user tries to resend activation code
        to the already activated user's email
        """
        user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), send_email=False, **self.user_info)

        profile = self.registration_profile.objects.get(user=user)
        activated = (self.registration_profile.objects
                     .activate_user(profile.activation_key))
        self.assertFalse(activated.is_active)

        self.assertFalse(self.registration_profile.objects.resend_activation_mail(
            email=self.user_info['email'],
            site=Site.objects.get_current(),
        ))
        # Outbox has one mail, admin approve mail

        self.assertEqual(len(mail.outbox), 1)
        admins_emails = [value[1] for value in settings.ADMINS]
        for email in mail.outbox[0].to:
            self.assertIn(email, admins_emails)

    def test_admin_approval_email(self):
        """
        ``SupervisedRegistrationManager.send_admin_approve_email`` sends an
        email to the site administrators

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.activated = True
        self.registration_profile.objects.send_admin_approve_email(
            new_user, Site.objects.get_current())
        self.assertEqual(len(mail.outbox), 1)
        admins_emails = [value[1] for value in settings.ADMINS]
        for email in mail.outbox[0].to:
            self.assertIn(email, admins_emails)

    def test_admin_approval_email_uses_registration_default_from_email(self):
        """
        ``SupervisedRegistrationManager.send_admin_approve_email``` sends an
        email.

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.activated = True
        self.registration_profile.objects.send_admin_approve_email(
            new_user, Site.objects.get_current())
        self.assertEqual(mail.outbox[0].from_email, 'registration@email.com')

    def test_admin_approval_email_falls_back_to_django_default_from_email(self):
        """
        ``SupervisedRegistrationManager.send_admin_approve_email`` sends an
        email.

        """
        settings.REGISTRATION_DEFAULT_FROM_EMAIL = None
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.activated = True
        self.registration_profile.objects.send_admin_approve_email(
            new_user, Site.objects.get_current())
        self.assertEqual(mail.outbox[0].from_email, 'django@email.com')

    def test_admin_approval_email_is_html_by_default(self):
        """
        ``SupervisedRegistrationProfile.send_activation_email`` sends an html
        email by default.

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.activated = True
        self.registration_profile.objects.send_admin_approve_email(
            new_user, Site.objects.get_current())

        self.assertEqual(len(mail.outbox[0].alternatives), 1)

    def test_admin_approval_email_is_plain_text_if_html_disabled(self):
        """
        ``SupervisedRegistrationProfile.send_activation_email`` sends a plain
        text email if settings.REGISTRATION_EMAIL_HTML is False.

        """
        settings.REGISTRATION_EMAIL_HTML = False
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.activated = True
        self.registration_profile.objects.send_admin_approve_email(
            new_user, Site.objects.get_current())

        self.assertEqual(len(mail.outbox[0].alternatives), 0)

    def test_admin_approval_complete_email(self):
        """
        ``SupervisedRegistrationManager.send_admin_approve_complete_email``
        sends an email to the approved user

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_admin_approve_complete_email(Site.objects.get_current())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user_info['email']])

    def test_admin_approval_complete_email_uses_registration_default_from_email(self):
        """
        ``SupervisedRegistrationManager.send_admin_approve_complete_email``
        sends an email

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_admin_approve_complete_email(Site.objects.get_current())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, 'registration@email.com')

    def test_admin_approval_complete_email_falls_back_to_django_default_from_email(self):
        """
        ``SupervisedRegistrationManager.send_admin_approve_complete_email``
        sends an email

        """
        settings.REGISTRATION_DEFAULT_FROM_EMAIL = None
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_admin_approve_complete_email(Site.objects.get_current())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, 'django@email.com')

    def test_admin_approval_complete_email_is_html_by_default(self):
        """
        ``SupervisedRegistrationProfile.send_admin_approve_complete_email``
        sends an html email by default.

        """
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_admin_approve_complete_email(Site.objects.get_current())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(mail.outbox[0].alternatives), 1)

    def test_admin_approval_complete_email_is_plain_text_if_html_disabled(self):
        """
        ``SupervisedRegistrationProfile.send_admin_approve_complete_email``
        sends a plain text email if settings.REGISTRATION_EMAIL_HTML is False.

        """
        settings.REGISTRATION_EMAIL_HTML = False
        new_user = UserModel().objects.create_user(**self.user_info)
        profile = self.registration_profile.objects.create_profile(new_user)
        profile.send_admin_approve_complete_email(Site.objects.get_current())
        self.assertEqual(len(mail.outbox), 1)

        self.assertEqual(len(mail.outbox[0].alternatives), 0)

    def test_valid_admin_approval(self):
        """
        Approving an already activated user's account makes the user
        active
        """

        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        activated = (self.registration_profile.objects
                     .activate_user(profile.activation_key))

        self.failUnless(isinstance(activated, UserModel()))

        user = self.registration_profile.objects.admin_approve_user(
            profile.id, Site.objects.get_current())
        self.failUnless(isinstance(user, UserModel()))
        self.assertEqual(user.is_active, True)

    def test_admin_approval_not_activated(self):
        """
        Approving a non activated user's account fails
        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)

        user = self.registration_profile.objects.admin_approve_user(
            profile.id, Site.objects.get_current())
        self.failIf(isinstance(user, UserModel()))
        self.assertEqual(user, False)
        self.assertEqual(profile.user.is_active, False)

    def test_admin_approval_already_approved(self):
        """
        Approving an already approved user's account returns the User model
        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        activated = (self.registration_profile.objects
                     .activate_user(profile.activation_key))

        self.failUnless(isinstance(activated, UserModel()))

        user = self.registration_profile.objects.admin_approve_user(
            profile.id, Site.objects.get_current())
        self.failUnless(isinstance(user, UserModel()))
        self.assertEqual(user.is_active, True)

    def test_admin_approval_nonexistent_id(self):
        """
        Approving a non existent user profile does nothing and returns False
        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)

        user = self.registration_profile.objects.admin_approve_user(
            profile.id, Site.objects.get_current())
        self.failIf(isinstance(user, UserModel()))
        self.assertEqual(user, False)

    def test_activation_already_activated(self):
        """
        Attempting to re-activate an already-activated account fails.

        """
        new_user = self.registration_profile.objects.create_inactive_user(
            site=Site.objects.get_current(), **self.user_info)
        profile = self.registration_profile.objects.get(user=new_user)
        self.registration_profile.objects.activate_user(profile.activation_key)

        profile = self.registration_profile.objects.get(user=new_user)
        self.assertEqual(self.registration_profile.objects.activate_user(
            profile.activation_key), False)
