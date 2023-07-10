import re


def get_method_name(path):
    return to_snake_case(path.split('/')[-1])


def get_python_type(openapi_type):
    return {
        'string': 'str',
        'integer': 'int',
        'number': 'float',
        'array': 'list',
        'boolean': 'bool',
    }.get(openapi_type, 'Unknown')


def to_snake_case(name):
    if isinstance(name, list):
        return [to_snake_case(n) for n in name]
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def get_method_description(method_info):
    if 'summary' in method_info:
        return method_info['summary']
    return 'No description provided'


def get_response_description(method_info):
    responses = method_info['responses']
    return ", ".join(f"{status}: {responses[status]['description']}" for status in responses)


def get_data_type(method_info):
    if 'requestBody' in method_info and 'content' in method_info['requestBody']:
        if 'application/json' in method_info['requestBody']['content'] and 'schema' in \
                method_info['requestBody']['content']['application/json']:
            if 'type' in method_info['requestBody']['content']['application/json']['schema']:
                return get_python_type(
                    method_info['requestBody']['content']['application/json']['schema']['type'])
            elif '$ref' in method_info['requestBody']['content']['application/json']['schema']:
                ref = method_info['requestBody']['content']['application/json']['schema']['$ref']
                class_name = f"data_classes.{ref.split('.')[-1]}"
                #                 properties = self.api_data['components']['schemas'][class_name]['properties']
                #                 generate_data_class(class_name, properties)
                return class_name
    return None


def check_has_multipart(method_info):
    if 'requestBody' in method_info and 'content' in method_info['requestBody']:
        if 'multipart/form-data' in method_info['requestBody']['content']:
            return True

    return False


def generate_method_code(method_name, method_description, parameters, method, tags, response_description, return_type,
                         path, data_type, has_multipart):
    code = f"    def {method_name}(\n"
    code += f"        self,\n"
    for param in parameters:
        param_name = param[0]
        param_type = param[2]
        if param_type.startswith("enums."):
            param_type = f"{param_type} | type({param_type}.value)"
        elif param_type.startswith("data_classes."):
            param_type = f"{param_type} | dict"
        if param[3] is not None:
            param_type = f"{param_type} | None = None"
        code += f"        {to_snake_case(param_name)}: {param_type},\n"

    if data_type is not None:
        code += f"        data: {data_type} | None = None,\n"
    if has_multipart:
        code += f"        files: list | None = None,\n"
    code = code.rstrip(',\n')
    code += "\n    ):\n"
    code += f"        \"\"\"\n"
    code += f"        {method_description}\n"
    code += f"        Request method: {method}\n"
    code += f"        Tags: {tags}\n\n"
    for param in parameters:
        code += f"        :param {to_snake_case(param[0])}: {param[1]}\n"
    if data_type is not None:
        code += f"        :param data: Request body data\n"
    if has_multipart:
        code += f"        :param files: List of file paths\n"
    code += f"        :return: {response_description}\n"
    code += f"        :rtype: {return_type}\n"
    code += f"        \"\"\"\n"
    url_path = '/'.join([part for part in path.strip('/').split('/')[2:]])

    # params
    params = [param for param in parameters if param[3] is None]
    formatted_param_strs = []
    for param in params:
        param_key = param[0]
        param_value = to_snake_case(param[0])
        param_type = param[2]
        if param_type.startswith("enums."):
            param_value = f"                {param_type}({param_value}).value\n" \
                          f"                if isinstance({param_value}, {param_type})\n" \
                          f"                else {param_value})\n"
        formatted_param_str = f"'{param_key}': {param_value}"
        formatted_param_strs.append(formatted_param_str)

    params_str = ',\n                '.join(formatted_param_strs)
    if len(params) > 0:
        params_str = f"\n                {params_str}\n            "

    # optional params
    optional_params = [param for param in parameters if param[3] is not None]
    formatted_optional_param_strs = []

    for param in optional_params:
        param_key = param[0]
        param_value = to_snake_case(param[0])
        param_type = param[2]
        if param_type.startswith("enums."):
            param_value = f"\n                    {param_type}({param_value}).value\n" \
                          f"                    if isinstance({param_value}, {param_type})\n" \
                          f"                    else {param_value}"
        formatted_optional_param_str = f"'{param_key}': {param_value}"
        formatted_optional_param_strs.append(formatted_optional_param_str)

    optional_params_str = ',\n                '.join(formatted_optional_param_strs)
    if len(optional_params) > 0:
        optional_params_str = f"\n                {optional_params_str}\n            "

    code += f"        url = self._url(\n"
    code += f"            '{url_path}',\n"
    code += f"            {{{params_str}}},\n"
    code += f"            {{{optional_params_str}}}\n"
    code += f"        )\n"

    url_str = "url"
    data_param_str = None
    if data_type:
        if data_type.startswith("data_classes."):
            data_param_str = "data=asdict(data) if is_dataclass(data) else data"
        else:
            data_param_str = "data=data"

    files_param_str = "files=files" if has_multipart else None
    should_return_str = "" if return_type == "None" else "return "
    session_params = ", ".join(item for item in [url_str, data_param_str, files_param_str] if item is not None)
    code += f"        {should_return_str}self._session.{method}({session_params})\n"
    return code


def get_ref_name(media_info):
    ref = media_info['schema']['$ref'].split('/')[-1]
    ref_parts = ref.split('.')
    if len(ref_parts) > 1 and ref_parts[-2] == 'Enums':
        enum_name = ref_parts[-1]
        return f"enums.{enum_name}"
    else:
        class_name = ref_parts[-1]
        return f"data_classes.{class_name}"


def get_parameters(method_info):
    parameters = []
    if 'parameters' in method_info:
        for parameter in method_info['parameters']:
            if 'description' in parameter:
                default_value = None
                param_type = 'Unknown'
                if 'Default:' in parameter['description'] or 'default' in parameter['schema']:
                    default_value = 'None'
                if 'schema' in parameter:
                    if 'type' in parameter['schema']:
                        param_type = get_python_type(parameter['schema']['type'])
                    elif '$ref' in parameter['schema']:
                        param_type = get_ref_name(parameter)
                    else:
                        print(parameter)
                parameters.append(
                    (parameter['name'], parameter['description'], param_type, default_value))
    return sorted(parameters, key=lambda x: x[3] is not None)


def get_return_type(responses):
    for status, response_info in responses.items():
        if 'content' in response_info:
            for media_type, media_info in response_info['content'].items():
                if 'schema' in media_info:
                    if 'type' in media_info['schema']:
                        return get_python_type(media_info['schema']['type'])
                    elif '$ref' in media_info['schema']:
                        return get_ref_name(media_info)
    return 'None'
