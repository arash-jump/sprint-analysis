<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="ie=edge">

    <style>
        body {
            padding: 50px;
            font-family: sans-serif;
        }

        .email-header {
            text-align: center;
            padding-bottom: 20px;
            border-bottom: 1px solid #ddd;
        }

        .email-header h1 {
            font-size: 24px;
            color: #333;
            margin: 0; /* removed the default margins to all sides */
        }

        .email-body {
            padding: 20px;
        }

        .email-body p {
            font-size: 16px;
            color: #666;
            line-height: 1.5;
            margin: 0 0 5px;
        }

        .email-body .name {
            font-weight: bold;
        }

        .email-footer {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }

        .email-footer p {
            font-size: 14px;
            color: #999;
            margin: 0;
        }

        .button {
            display: inline-block;
            padding: 10px 20px;
            margin: 20px 0;
            background-color: #0d6efd;
            color: #fff;
            text-decoration: none;
            font-size: 16px;
            border-radius: 5px;
        }

        .email-body .not-me {
            margin-top: 25px;
            font-style: italic;
            font-size: 14px;
        }

    </style>
</head>
<body>
    <div class="email-header">
        <h1>Welcome to Insta App</h1>
    </div>

    <div class="email-body">
        <p class="name">Hi {{ $name }}</p>
        <p>Thank you for signing up to Insta app. We're excited to have you on board!</p>
        <p>To get started, please confirm your email address by cliccking the button below:</p>

        {{-- Blue Button / Confirm Button--}}
        <p><a href="{{ $app_url }}" class="button">Confirm Email Address</a></p>

        <p>Best regards, <br>Kredo Team</p>

        <p class="not-me">If you did not sign up for this account, you can ignore this email.</p>
    </div>
    <div class="email-footer">
        <p>&copy; 2025 Kredo Insta App. All rights reserved.</p>
    </div>
</body>
</html>