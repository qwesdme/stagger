import json
import os

from helpers.openapi_helpers import *


class OpenAPIToPython:
    def __init__(self, openapi_json_path):
        self.method_codes = []
        self.enums = {}
        self.data_classes = {}
        self.openapi_json_path = openapi_json_path
        self.api_data = self.load_openapi_json()

    def load_openapi_json(self):
        with open(self.openapi_json_path, 'r') as f:
            data = json.load(f)
        return data

    def handle_ref_schemas(self):
        os.makedirs("output/helpers", exist_ok=True)
        with open('output/helpers/data_classes.py', 'w') as f:
            f.write(f"from dataclasses import dataclass\n")
        with open('output/helpers/enums.py', 'w') as f:
            f.write("from enum import Enum\n")

        for schema, info in self.api_data['components']['schemas'].items():
            class_name_split = schema.split('.')
            class_name = class_name_split[-1]
            if class_name_split[-2] == 'Enums':
                enum_values = info['enum']
                enum_type = get_python_type(info['type'])
                os.makedirs("output/helpers", exist_ok=True)
                with open('output/helpers/enums.py', 'a') as f:
                    f.write(f"\n\nclass {class_name}(Enum):\n")
                    for value in enum_values:
                        if enum_type == 'str':
                            f.write(f"    {value} = '{value}'\n")
                        else:
                            print(enum_type)
                            f.write(f"    {value} = {value}\n")
            else:
                self.write_ref_class(class_name, info)

    def write_data_classes(self):
        os.makedirs("output/helpers", exist_ok=True)
        with open('output/helpers/data_classes.py', 'w') as f:
            f.write(f"from dataclasses import dataclass\n")
            for schema, info in self.api_data['components']['schemas'].items():
                self.write_ref_class(schema, info)

    def write_ref_class(self, schema, info):
        class_name_split = schema.split('.')
        class_name = class_name_split[-1]
        class_header = f"\n\n@dataclass\n" \
                       f"class {class_name}:\n"
        class_attrs = []
        for prop_name, prop_info in info['properties'].items():
            if 'type' in prop_info:
                prop_type = get_python_type(prop_info['type'])
            elif '$ref' in prop_info:
                ref = prop_info['$ref']
                schema = ref.split('/')[-1]
                info = self.api_data['components']['schemas'][schema]
                self.write_ref_class(schema, info)
                prop_type = prop_info['$ref'].split('.')[-1]
            else:
                prop_type = "Unknown"
            class_attrs.append(f"    {prop_name}: {prop_type}\n")
        with open('output/helpers/data_classes.py', 'a') as f:
            f.write(class_header)
            for class_attr in class_attrs:
                f.write(class_attr)

    def generate_python_code(self):
        os.makedirs("output", exist_ok=True)
        self.handle_interface_class()
        self.handle_ref_schemas()
        self.write_interface_class()

    def handle_interface_class(self):
        for path, path_info in self.api_data['paths'].items():
            for method, method_info in path_info.items():
                method_name = get_method_name(path)
                method_description = get_method_description(method_info)
                parameters = get_parameters(method_info)
                tags = ', '.join(method_info['tags'])
                response_description = get_response_description(method_info)
                return_type = get_return_type(method_info['responses'])
                data_type = get_data_type(method_info)
                has_multipart = check_has_multipart(method_info)

                self.method_codes.append(
                    generate_method_code(
                        method_name, method_description, parameters, method, tags, response_description, return_type,
                        path, data_type, has_multipart
                    )
                )

    def write_interface_class(self):
        class_header = "class APIInterface:\n" \
                       "    def __init__(self, session, base_url):\n" \
                       "        self._session = session\n" \
                       "        self._base_url = base_url\n\n" \
                       "    def _url(self, path, params, optional_params):\n" \
                       "        for k, v in optional_params:\n" \
                       "            if v is None:\n" \
                       "                del optional_params[k]\n" \
                       "        params_str = '&'.join([f'{k}={v}' for k, v in {**params, **optional_params}.items()])\n" \
                       "        return f'{self._base_url}/{path}?{params_str}'\n"

        with open('output/api_interface.py', 'w') as f:
            f.write(
                "from helpers import enums\n"
                "from dataclasses import asdict, is_dataclass\n"
                "from helpers import data_classes\n\n\n"
            )
            f.write(class_header)
            for i, method_code in enumerate(self.method_codes):
                if i < len(self.method_codes):
                    f.write('\n')
                f.write(method_code)


if __name__ == "__main__":
    openapi_to_python = OpenAPIToPython('openapi.json')
    openapi_to_python.generate_python_code()
