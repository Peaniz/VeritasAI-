import grpc
from concurrent import futures
from src.settings import settings
from src.services.auth_service import AuthService

# grpc_generated stubs are generated from proto; import conditionally
try:
    from src.grpc_generated import auth_pb2, auth_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False


auth_svc = AuthService()


class AuthServicer:
    """gRPC servicer for AuthService."""

    def ValidateToken(self, request, context):
        if not GRPC_AVAILABLE:
            context.abort(grpc.StatusCode.UNAVAILABLE, "gRPC stubs not generated")
            return

        payload = auth_svc.validate_token(request.token)
        if not payload:
            return auth_pb2.ValidateTokenResponse(valid=False)

        return auth_pb2.ValidateTokenResponse(
            valid=True,
            user_id=payload.get("sub", ""),
            email=payload.get("email", ""),
            role=payload.get("role", ""),
            plan=payload.get("plan", ""),
        )

    def GetUser(self, request, context):
        if not GRPC_AVAILABLE:
            context.abort(grpc.StatusCode.UNAVAILABLE, "gRPC stubs not generated")
            return

        user = auth_svc.get_user_by_id(request.user_id)
        if not user:
            context.abort(grpc.StatusCode.NOT_FOUND, "User not found")
            return

        return auth_pb2.UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            plan=user.plan,
            is_verified=user.is_verified,
            created_at=user.created_at.isoformat(),
        )


def serve_grpc():
    if not GRPC_AVAILABLE:
        import logging
        logging.warning("gRPC stubs not found; run 'make proto' to generate them")
        return

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = AuthServicer()
    auth_pb2_grpc.add_AuthServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f"[::]:{settings.grpc_port}")
    server.start()
    return server
