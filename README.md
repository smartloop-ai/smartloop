
<img src="https://github.com/user-attachments/assets/b30e2c38-dc19-49a5-973d-51e1dafe5c4d" width="100%" />

<br/>

Use the CLI to upload, manage, and query documents based on fine-tuned LLM models. It uses the smartloop API to manage projects and documents and gives you an easy way to quickly process contents and reason based on it.


![PyPI - Version](https://img.shields.io/pypi/v/smartloop)

## Requirements

- Python 3.11

## Installation

Install the CLI with the following command:

```
pip install -U smartloop

```
Once installed, check that everything is setup correctly:

![image](https://github.com/user-attachments/assets/0a4e0221-d2f7-4f87-9fb2-5e4ce7a23f62)


## Setup
First you will need to create a free [account](https://app.smartloop.ai/signup), verify and configure your account. Once verified, copy your [developer token](https://app.smartloop.ai/developer) to the clipboard. You will need a invitation code as of writing this document, please reach out to us at `hello@smartloop.ai` and we should be able to get you started.

Once you have your token, run the following command in your terminal:

```bash
smartloop login
```

This command will prompt you for your token, copy and pase the token that you have received in your email. Next step it to create a  project, you can do so with the following command:

```bash
smartloop project create --name microsoft
```

To get the project Id , use the following, the will also show you the currently selected project:

```bash
smartloop project list
```

To delete a project, use:

```bash
smartloop project delete --id=project_id
```

## Upload Document

Once the project is created , upload documents from your folder or a specific file, in this case I am uploading the a document describing Microsoft online services form my local machine

```bash
smartloop upload --id=<project_id> --path=~/document1.pdf
```



## Select a project

Use the following command to interactively select a project:


```bash
smartloop project select
```

## Run It

Finally, once project is selected, document you have uploaded and processed, run the CLI to prompt:

```bash
smartloop run
```

This will bring up the prompt to query your information from your uploaded document

```bash
Current project: Microsoft(microsoft-24-07-2024)
Enter message (Ctrl-C to exit): what the SLA for azure open ai
⠋
The SLA (Service Level Agreement) for Azure OpenAI is not explicitly mentioned in the provided text. However, it's possible that the SLA for Azure OpenAI might be similar to the one mentioned below:

"Uptime Percentage"

* Service Credit:
+ < 99.9%: 10%
+ < 99%: 25%
+ < 95%: 100%

Please note that this is not a direct quote from the provided text, but rather an inference based on the format and structure of the SLA mentioned for other Azure services (e.g., SAP HANA on Azure High Availability Pair). To confirm the actual SLA for Azure OpenAI, you should check the official Microsoft documentation or contact their support team.

Enter message (Ctrl-C to exit):
```

In order to set `temperature` of your conversation, which ranges from 0.0 to 1.0, use the following command:

```bash 
smartloop project set --id=project_id --temp=0.3

```

`LLM temperature is a parameter that influences the language model's output, determining whether the output is more random and creative or more predictable.`

The higher value tends towards more creative answer

## Supported Documents types

* PDF
* DOCX
* TXT
* CSV (soon)


## Contributing

Contributions are welcome! Please create a pull request with your changes. 


## Contact

If you have any questions or suggestions, please feel free to reach out to hello@smartloop.ai


## References

* [Smartloop API Documentation](https://api.smartloop.ai/v1/redoc)
* [Meta LLaMA](https://research.facebook.com/publications/llama-open-and-efficient-foundation-language-models/)
* [LoRA](https://arxiv.org/abs/2106.09685)



## License

This project is licensed under the terms of the MIT license.
