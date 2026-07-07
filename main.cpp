#include <iostream>
#include <vector>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>
#include <opencv2/opencv.hpp>
#include <opencv2/dnn.hpp>

int main() {
    std::cout << "====================================================" << std::endl;
    std::cout << " Initializing Secure Edge AI Metadata Node          " << std::endl;
    std::cout << "====================================================" << std::endl;

    cv::dnn::Net net = cv::dnn::readNetFromCaffe("/mnt/sandbox/deploy.prototxt", "/mnt/sandbox/mobilenet_iter_73000.caffemodel");

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in serv_addr;
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(9999);
    serv_addr.sin_addr.s_addr = inet_addr("10.0.2.2"); 

    std::cout << "[EDGE NODE] Connecting to Mac..." << std::endl;
    while (connect(sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) < 0) {
        usleep(500000);
    }

    std::vector<unsigned char> stream_buffer;
    uint32_t msg_size = 0;

    while (true) {
        while (stream_buffer.size() < 4) {
            char temp_buf[4096];
            int bytes_read = recv(sock, temp_buf, sizeof(temp_buf), 0);
            if (bytes_read <= 0) return 0;
            stream_buffer.insert(stream_buffer.end(), temp_buf, temp_buf + bytes_read);
        }

        std::memcpy(&msg_size, stream_buffer.data(), 4);
        msg_size = ntohl(msg_size);
        stream_buffer.erase(stream_buffer.begin(), stream_buffer.begin() + 4);

        while (stream_buffer.size() < msg_size) {
            char temp_buf[65536];
            int bytes_read = recv(sock, temp_buf, sizeof(temp_buf), 0);
            if (bytes_read <= 0) return 0;
            stream_buffer.insert(stream_buffer.end(), temp_buf, temp_buf + bytes_read);
        }

        std::vector<unsigned char> jpeg_bytes(stream_buffer.begin(), stream_buffer.begin() + msg_size);
        stream_buffer.erase(stream_buffer.begin(), stream_buffer.begin() + msg_size);

        cv::Mat frame = cv::imdecode(jpeg_bytes, cv::IMREAD_COLOR);
        if (!frame.empty()) {
            cv::Mat blob = cv::dnn::blobFromImage(frame, 0.007843, cv::Size(300, 300), cv::Scalar(127.5, 127.5, 127.5), false);
            net.setInput(blob);
            cv::Mat detection = net.forward();
            cv::Mat detectionMat(detection.size[2], detection.size[3], CV_32F, detection.ptr<float>());

            std::string coord_data = "";
            for (int i = 0; i < detectionMat.rows; i++) {
                float confidence = detectionMat.at<float>(i, 2);
                
                // Only bundle objects detected with > 50% confidence
                if (confidence > 0.5) {
                    int class_id = static_cast<int>(detectionMat.at<float>(i, 1));
                    float x1 = detectionMat.at<float>(i, 3);
                    float y1 = detectionMat.at<float>(i, 4);
                    float x2 = detectionMat.at<float>(i, 5);
                    float y2 = detectionMat.at<float>(i, 6);
                    
                    // Format: class,confidence,x1,y1,x2,y2|
                    coord_data += std::to_string(class_id) + "," + 
                                  std::to_string(confidence) + "," + 
                                  std::to_string(x1) + "," + 
                                  std::to_string(y1) + "," + 
                                  std::to_string(x2) + "," + 
                                  std::to_string(y2) + "|";
                }
            }
            if(coord_data.empty()) coord_data = "none";

            uint32_t out_size = htonl(coord_data.length());
            send(sock, &out_size, 4, 0);
            send(sock, coord_data.c_str(), coord_data.length(), 0);
        }
    }
    close(sock);
    return 0;
}