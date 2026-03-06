from typing import Type, TypeVar, Dict, Any

T = TypeVar('T')

class Container:
    """Simple Dependency Injection Container."""
    
    _services: Dict[Type, Any] = {}
    _instances: Dict[Type, Any] = {}

    @classmethod
    def register(cls, interface: Type[T], implementation: Any, singleton: bool = True) -> None:
        cls._services[interface] = {
            "impl": implementation,
            "singleton": singleton
        }

    @classmethod
    def resolve(cls, interface: Type[T]) -> T:
        if interface not in cls._services:
            raise KeyError(f"Service {interface} not registered.")
            
        service_info = cls._services[interface]
        
        if service_info["singleton"]:
            if interface not in cls._instances:
                impl = service_info["impl"]
                cls._instances[interface] = impl() if callable(impl) else impl
            return cls._instances[interface]
        else:
            impl = service_info["impl"]
            return impl() if callable(impl) else impl

    @classmethod
    def clear(cls):
        cls._services.clear()
        cls._instances.clear()
