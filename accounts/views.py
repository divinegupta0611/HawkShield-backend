from django.shortcuts import render

# Create your views here.
from google.oauth2 import id_token
from google.auth.transport import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
import jwt
import datetime
import os
from dotenv import load_dotenv
load_dotenv()  # loads variables from .env

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET")

@api_view(["POST"])
def google_login(request):
    token = request.data.get("token")

    try:
        payload = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        email = payload["email"]
        name = payload.get("name")
        picture = payload.get("picture")

        user, created = User.objects.get_or_create(
            username=email, defaults={"email": email, "first_name": name}
        )

        jwt_token = jwt.encode(
            {
                "user_id": user.id,
                "email": email,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
            },
            JWT_SECRET,
            algorithm="HS256"
        )

        return Response({
            "success": True,
            "token": jwt_token,
            "user": {"email": email, "name": name, "picture": picture}
        })

    except Exception as e:
        print(e)
        return Response({"error": "Invalid Google token"}, status=400)